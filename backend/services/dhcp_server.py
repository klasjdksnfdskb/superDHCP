"""
DHCP 协议服务主进程 — 异步 UDP 服务
同时处理 DHCPv4 (port 67) 和 DHCPv6 (port 547)

架构:
- 多进程 UDP 监听 (可配置 worker 数量)
- 每个 worker 异步处理 DHCP 请求
- 通过 VLAN ID / Relay Agent 绑定地址池
- 租约记录写入 PostgreSQL
"""

import asyncio
import logging
from typing import Optional
from app_settings import settings
from .dhcpv4 import DHCPPacket, DHCPv4Engine, DHCPDISCOVER, DHCPREQUEST, DHCPRELEASE, DHCPINFORM
from .dhcpv6 import DHCPv6Packet, DHCPv6Engine, SOLICIT, REQUEST, RENEW, RELEASE, INFORMATION_REQUEST
from .pool_manager import PoolManager
from .lease_manager import LeaseManager
from models.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class DHCPServer:
    """
    DHCP 协议服务
    
    启动独立的异步事件循环处理 DHCP 请求
    """

    def __init__(self):
        self.dhcpv4 = None
        self.dhcpv6 = None
        self.running = False

    async def start(self):
        """启动 DHCP 服务"""
        self.running = True
        tasks = []

        if settings.DHCPV4_ENABLED:
            tasks.append(self._start_dhcpv4())

        if settings.DHCPV6_ENABLED:
            tasks.append(self._start_dhcpv6())

        if tasks:
            logger.info(f"DHCP 服务启动: DHCPv4={settings.DHCPV4_ENABLED} DHCPv6={settings.DHCPV6_ENABLED}")
            await asyncio.gather(*tasks)

    async def stop(self):
        """停止 DHCP 服务"""
        self.running = False
        if self.dhcpv4:
            self.dhcpv4.close()
        if self.dhcpv6:
            self.dhcpv6.close()

    # ─── DHCPv4 ───

    async def _start_dhcpv4(self):
        """启动 DHCPv4 UDP 监听"""
        try:
            # 创建 UDP socket
            transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
                lambda: DHCPv4Protocol(),
                local_addr=('0.0.0.0', settings.DHCPV4_SERVER_PORT),
                allow_broadcast=True,
            )
            self.dhcpv4 = transport
            logger.info(f"DHCPv4 监听 0.0.0.0:{settings.DHCPV4_SERVER_PORT}")

            # 保持监听
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"DHCPv4 服务异常: {e}", exc_info=True)
        finally:
            if self.dhcpv4:
                self.dhcpv4.close()

    # ─── DHCPv6 ───

    async def _start_dhcpv6(self):
        """启动 DHCPv6 UDP 监听"""
        try:
            transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
                lambda: DHCPv6Protocol(),
                local_addr=('::', settings.DHCPV6_SERVER_PORT),
            )
            self.dhcpv6 = transport
            logger.info(f"DHCPv6 监听 [::]:{settings.DHCPV6_SERVER_PORT}")

            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"DHCPv6 服务异常: {e}", exc_info=True)
        finally:
            if self.dhcpv6:
                self.dhcpv6.close()


class DHCPv4Protocol(asyncio.DatagramProtocol):
    """DHCPv4 UDP 协议处理器"""

    def __init__(self):
        self.transport = None
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport
        logger.info("DHCPv4 UDP 连接建立")

    def datagram_received(self, data: bytes, addr):
        """收到 DHCPv4 请求"""
        asyncio.ensure_future(self._handle(data, addr))

    async def _handle(self, data: bytes, addr):
        """异步处理 DHCPv4 请求"""
        try:
            pkt = DHCPPacket(data)

            async with AsyncSessionLocal() as session:
                pool_mgr = PoolManager(session)
                lease_mgr = LeaseManager(session)
                engine = DHCPv4Engine(pool_mgr, lease_mgr)

                # 提取 VLAN (Option 82 或 Relay Agent 推断)
                vlan_id = self._extract_vlan(pkt)

                msg_type = pkt.message_type
                logger.debug(f"DHCPv4: type={msg_type} MAC={pkt.client_mac} VLAN={vlan_id}")

                if msg_type == DHCPDISCOVER:
                    result = await engine.handle_discover(pkt, vlan_id)
                    if result:
                        resp, ip, lease_time = result
                        response_pkt = resp.build(
                            yiaddr=ip,
                            server_id=settings.DHCPV4_INTERFACE,
                            lease_time=lease_time
                        )
                        self.transport.sendto(response_pkt, (addr[0], 68))
                        logger.info(f"DHCPOFFER: {ip} → MAC={pkt.client_mac}")

                elif msg_type == DHCPREQUEST:
                    result = await engine.handle_request(pkt, vlan_id)
                    if result:
                        resp, ip, lease_time = result
                        if resp.msg_type == 5:  # ACK
                            response_pkt = resp.build(
                                yiaddr=ip,
                                server_id=settings.DHCPV4_INTERFACE,
                                lease_time=lease_time
                            )
                            self.transport.sendto(response_pkt, (addr[0], 68))
                            logger.info(f"DHCPACK: {ip} → MAC={pkt.client_mac}")
                        else:
                            response_pkt = resp.build(server_id=settings.DHCPV4_INTERFACE)
                            self.transport.sendto(response_pkt, (addr[0], 68))
                            logger.warning(f"DHCPNAK: MAC={pkt.client_mac}")

                elif msg_type == DHCPRELEASE:
                    await engine.handle_release(pkt)
                    logger.info(f"DHCPRELEASE: MAC={pkt.client_mac}")

                elif msg_type == DHCPINFORM:
                    resp = await engine.handle_inform(pkt, vlan_id)
                    if resp:
                        response_pkt = resp.build(server_id=settings.DHCPV4_INTERFACE)
                        self.transport.sendto(response_pkt, (addr[0], 68))

        except Exception as e:
            logger.error(f"DHCPv4 处理异常: {e}", exc_info=True)

    @staticmethod
    def _extract_vlan(pkt: DHCPPacket) -> Optional[int]:
        """从 Option 82 / Relay Agent 提取 VLAN ID"""
        # Option 82 Circuit ID 可能编码 VLAN
        circuit_id, _ = pkt.get_relay_agent_info()
        if circuit_id and len(circuit_id) >= 4:
            try:
                # 假设 Circuit ID 末2字节为 VLAN ID
                vlan = int(circuit_id[-4:], 16)
                return vlan
            except ValueError:
                pass
        return None


class DHCPv6Protocol(asyncio.DatagramProtocol):
    """DHCPv6 UDP 协议处理器"""

    def __init__(self):
        self.transport = None
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport
        logger.info("DHCPv6 UDP 连接建立")

    def datagram_received(self, data: bytes, addr):
        """收到 DHCPv6 请求"""
        asyncio.ensure_future(self._handle(data, addr))

    async def _handle(self, data: bytes, addr):
        """异步处理 DHCPv6 请求"""
        try:
            pkt = DHCPv6Packet(data)
            client_mac = pkt.extract_mac_from_duid()

            async with AsyncSessionLocal() as session:
                pool_mgr = PoolManager(session)
                lease_mgr = LeaseManager(session)
                engine = DHCPv6Engine(pool_mgr, lease_mgr)

                vlan_id = None  # DHCPv6 VLAN 需通过 Relay 提取
                msg_type = pkt.msg_type

                logger.debug(f"DHCPv6: type={msg_type} MAC={client_mac}")

                if msg_type == SOLICIT:
                    result = await engine.handle_solicit(pkt, vlan_id, client_mac)
                    if result:
                        resp, addr_assigned, mode = result
                        self.transport.sendto(resp.build(), addr)
                        logger.info(f"DHCPv6 ADVERTISE: {addr_assigned} mode={mode}")

                elif msg_type == REQUEST:
                    result = await engine.handle_request(pkt, vlan_id, client_mac)
                    if result:
                        resp, addr_assigned, mode = result
                        self.transport.sendto(resp.build(), addr)
                        logger.info(f"DHCPv6 REPLY: {addr_assigned} mode={mode}")

                elif msg_type == RENEW:
                    resp = await engine.handle_renew(pkt, client_mac)
                    if resp:
                        self.transport.sendto(resp.build(), addr)

                elif msg_type == RELEASE:
                    resp = await engine.handle_release(pkt, client_mac)
                    if resp:
                        self.transport.sendto(resp.build(), addr)

                elif msg_type == INFORMATION_REQUEST:
                    resp = await engine.handle_information_request(pkt, vlan_id, client_mac)
                    if resp:
                        self.transport.sendto(resp.build(), addr)
                        logger.info(f"DHCPv6 INFO-REPLY (stateless) MAC={client_mac}")

        except Exception as e:
            logger.error(f"DHCPv6 处理异常: {e}", exc_info=True)


def run_dhcp_server():
    """独立进程入口 — DHCP 协议服务"""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )

    server = DHCPServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        asyncio.run(server.stop())


if __name__ == "__main__":
    run_dhcp_server()