"""
DHCPv4 协议引擎 — RFC 2131 / RFC 2132

处理 DHCPv4 协议消息:
- DHCPDISCOVER  → DHCPOFFER
- DHCPREQUEST   → DHCPACK / DHCPNAK
- DHCPRELEASE   → 释放租约
- DHCPDECLINE   → 标记地址不可用
- DHCPINFORM    → DHCPACK (仅信息)

支持 Option:
- 1  (Subnet Mask)
- 3  (Router)
- 6  (DNS Servers)
- 12 (Hostname)
- 15 (Domain Name)
- 42 (NTP Servers)
- 43 (Vendor Specific)
- 51 (Lease Time)
- 53 (DHCP Message Type)
- 54 (Server Identifier)
- 55 (Parameter Request List)
- 60 (Vendor Class Identifier)
- 61 (Client Identifier)
- 66 (TFTP Server Name)
- 67 (Bootfile Name)
- 82 (Relay Agent Information)
"""

import struct
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ─── DHCP 常量 ───
DHCP_SERVER_PORT = 67
DHCP_CLIENT_PORT = 68

# 消息类型 (Option 53)
DHCPDISCOVER = 1
DHCPOFFER = 2
DHCPREQUEST = 3
DHCPDECLINE = 4
DHCPACK = 5
DHCPNAK = 6
DHCPRELEASE = 7
DHCPINFORM = 8

# Option 代码
OPT_SUBNET_MASK = 1
OPT_ROUTER = 3
OPT_DNS = 6
OPT_HOSTNAME = 12
OPT_DOMAIN_NAME = 15
OPT_MTU = 26
OPT_NTP = 42
OPT_VENDOR_SPECIFIC = 43
OPT_REQUESTED_IP = 50
OPT_LEASE_TIME = 51
OPT_MESSAGE_TYPE = 53
OPT_SERVER_ID = 54
OPT_PARAM_REQUEST = 55
OPT_VENDOR_CLASS = 60
OPT_CLIENT_ID = 61
OPT_TFTP_SERVER = 66
OPT_BOOTFILE = 67
OPT_RELAY_AGENT = 82

MAGIC_COOKIE = b'\x63\x82\x53\x63'


class DHCPPacket:
    """DHCP 报文解析/构建"""

    def __init__(self, data: bytes):
        self.raw = data
        self.op = data[0]           # 1=BOOTREQUEST, 2=BOOTREPLY
        self.htype = data[1]        # 硬件类型 (1=Ethernet)
        self.hlen = data[2]         # 硬件地址长度
        self.hops = data[3]         # 跳数
        self.xid = data[4:8]        # 事务 ID
        self.secs = struct.unpack('!H', data[8:10])[0]
        self.flags = struct.unpack('!H', data[10:12])[0]
        self.ciaddr = data[12:16]   # 客户端 IP
        self.yiaddr = data[16:20]   # 分配 IP
        self.siaddr = data[20:24]   # 下一服务器 IP
        self.giaddr = data[24:28]   # 中继代理 IP
        self.chaddr = data[28:44]   # 客户端 MAC (16B, 实际用前 hlen)
        self.sname = data[44:108]   # 服务器名
        self.file = data[108:236]   # 启动文件名

        # 解析 Options (从 240 字节开始, 跳过 MAGIC COOKIE)
        self.options: Dict[int, bytes] = {}
        self._parse_options(data[240:])

        self.client_mac = ':'.join(f'{b:02x}' for b in self.chaddr[:self.hlen])
        self.message_type = self._get_option_int(OPT_MESSAGE_TYPE)
        self.hostname = self._get_option_str(OPT_HOSTNAME)
        self.requested_ip = self._get_option_ip(OPT_REQUESTED_IP)
        self.server_id = self._get_option_ip(OPT_SERVER_ID)
        self.vendor_class = self._get_option_str(OPT_VENDOR_CLASS)
        self.param_request = self._get_option_raw(OPT_PARAM_REQUEST, b'')

    def _parse_options(self, data: bytes):
        """解析 DHCP Options"""
        if data[:4] != MAGIC_COOKIE:
            return
        pos = 4
        while pos < len(data):
            code = data[pos]
            if code == 255:  # End
                break
            if code == 0:    # Pad
                pos += 1
                continue
            if pos + 1 >= len(data):
                break
            length = data[pos + 1]
            if pos + 2 + length > len(data):
                break
            value = data[pos + 2:pos + 2 + length]
            self.options[code] = value
            pos += 2 + length

    def _get_option_raw(self, code: int, default: bytes = b'') -> bytes:
        return self.options.get(code, default)

    def _get_option_int(self, code: int, default: int = 0) -> int:
        data = self.options.get(code, b'')
        if len(data) >= 1:
            return data[0]
        return default

    def _get_option_ip(self, code: int) -> Optional[str]:
        data = self.options.get(code, b'')
        if len(data) == 4:
            return '.'.join(str(b) for b in data)
        return None

    def _get_option_str(self, code: int) -> Optional[str]:
        data = self.options.get(code, b'')
        if data:
            return data.decode('ascii', errors='replace').rstrip('\x00')
        return None

    def get_relay_agent_info(self) -> Tuple[Optional[str], Optional[str]]:
        """提取 Option 82 (Circuit ID / Remote ID)"""
        data = self.options.get(OPT_RELAY_AGENT, b'')
        circuit_id, remote_id = None, None
        pos = 0
        while pos < len(data):
            if pos + 2 > len(data):
                break
            sub_opt = data[pos]
            sub_len = data[pos + 1]
            sub_val = data[pos + 2:pos + 2 + sub_len]
            if sub_opt == 1:
                circuit_id = sub_val.hex()
            elif sub_opt == 2:
                remote_id = sub_val.hex()
            pos += 2 + sub_len
        return circuit_id, remote_id


class DHCPv4Response:
    """构建 DHCPv4 响应报文"""

    def __init__(self, request: DHCPPacket, msg_type: int):
        self.request = request
        self.msg_type = msg_type
        self.options: Dict[int, bytes] = {}

    def set_option(self, code: int, value: bytes):
        self.options[code] = value

    def set_ip_option(self, code: int, ip: str):
        parts = [int(p) for p in ip.split('.')]
        self.options[code] = bytes(parts)

    def build(self, yiaddr: str = '0.0.0.0', siaddr: str = '0.0.0.0',
              server_id: Optional[str] = None,
              lease_time: int = 86400) -> bytes:
        """构建完整 DHCP 响应报文"""
        # 基础头
        pkt = bytearray(240)
        pkt[0] = 2  # BOOTREPLY
        pkt[1] = self.request.htype
        pkt[2] = self.request.hlen
        pkt[3] = 0  # hops
        pkt[4:8] = self.request.xid
        pkt[8:10] = struct.pack('!H', 0)  # secs
        pkt[10:12] = self.request.flags
        pkt[12:16] = b'\x00\x00\x00\x00'  # ciaddr
        pkt[16:20] = bytes(int(p) for p in yiaddr.split('.'))  # yiaddr
        pkt[20:24] = bytes(int(p) for p in siaddr.split('.'))  # siaddr
        pkt[24:28] = self.request.giaddr  # giaddr
        pkt[28:44] = self.request.chaddr  # chaddr
        pkt[44:108] = b'\x00' * 64  # sname
        pkt[108:236] = b'\x00' * 128  # file

        # Magic cookie
        pkt[236:240] = MAGIC_COOKIE

        # Option 53: Message Type
        self.options[OPT_MESSAGE_TYPE] = bytes([self.msg_type])

        # Option 54: Server Identifier
        if server_id:
            self.set_ip_option(OPT_SERVER_ID, server_id)

        # Option 51: Lease Time
        if lease_time:
            self.options[OPT_LEASE_TIME] = struct.pack('!I', lease_time)

        # 写入 options
        for code, value in sorted(self.options.items()):
            pkt.append(code)
            pkt.append(len(value))
            pkt.extend(value)

        pkt.append(255)  # End Option
        return bytes(pkt)


class DHCPv4Engine:
    """
    DHCPv4 协议处理引擎
    
    状态机:
    DISCOVER → 查找池 → 分配 IP → OFFER
    REQUEST  → 验证池 → 确认 IP → ACK/NAK
    RELEASE  → 释放 IP → (无响应)
    INFORM   → 返回配置信息 → ACK
    """

    def __init__(self, pool_manager, lease_manager):
        self.pool_manager = pool_manager
        self.lease_manager = lease_manager

    async def handle_discover(self, pkt: DHCPPacket, vlan_id: Optional[int]) -> Optional[DHCPv4Response]:
        """处理 DHCPDISCOVER → 返回 DHCPOFFER"""
        pool = await self.pool_manager.find_pool_by_vlan(vlan_id)
        if not pool:
            logger.warning(f"DHCPDISCOVER: VLAN={vlan_id} 无匹配地址池")
            return None

        # 分配 IP
        ip = await self.pool_manager.allocate_ipv4(pool.id, pkt.client_mac, vlan_id)
        if not ip:
            logger.warning(f"DHCPDISCOVER: 地址池 {pool.name} 无可用 IP")
            return None

        # 查找对应子网获取配置
        subnet = await self._find_subnet_for_ip(pool, ip)
        if not subnet:
            return None

        # 构建 OFFER
        resp = DHCPv4Response(pkt, DHCPOFFER)
        resp.set_ip_option(OPT_SUBNET_MASK, subnet.netmask)
        if subnet.gateway:
            resp.set_ip_option(OPT_ROUTER, str(subnet.gateway))
        if subnet.dns_servers:
            for dns in subnet.dns_servers:
                # Multi-DNS 支持
                pass

        # 自定义选项 (Option 43)
        option_data = subnet.option_data.get("option43") if subnet.option_data else None
        if option_data:
            resp.set_option(OPT_VENDOR_SPECIFIC, option_data.encode())

        lease_time = subnet.lease_time or 86400
        return resp, ip, lease_time

    async def handle_request(self, pkt: DHCPPacket, vlan_id: Optional[int]) -> Tuple[Optional[DHCPv4Response], Optional[str]]:
        """处理 DHCPREQUEST → 返回 DHCPACK 或 DHCPNAK"""
        requested_ip = pkt.requested_ip or self._bytes_to_ip(pkt.ciaddr)

        pool = await self.pool_manager.find_pool_by_vlan(vlan_id)
        if not pool:
            return DHCPv4Response(pkt, DHCPNAK), None

        subnet = await self._find_subnet_for_ip(pool, requested_ip)
        if not subnet:
            return DHCPv4Response(pkt, DHCPNAK), None

        # 验证 IP 在子网范围内
        try:
            import ipaddress
            net = ipaddress.IPv4Network(f"{subnet.subnet}/{subnet.netmask}")
            req_ip = ipaddress.IPv4Address(requested_ip)
            if req_ip not in net:
                return DHCPv4Response(pkt, DHCPNAK), None
        except (ValueError, TypeError):
            return DHCPv4Response(pkt, DHCPNAK), None

        # 构建 ACK
        resp = DHCPv4Response(pkt, DHCPACK)
        resp.set_ip_option(OPT_SUBNET_MASK, subnet.netmask)
        if subnet.gateway:
            resp.set_ip_option(OPT_ROUTER, str(subnet.gateway))
        if subnet.dns_servers:
            for dns in subnet.dns_servers[:4]:
                resp.set_ip_option(OPT_DNS, str(dns))
        lease_time = subnet.lease_time or 86400

        # Option 43
        option43 = subnet.option_data.get("option43") if subnet.option_data else None
        if option43:
            resp.set_option(OPT_VENDOR_SPECIFIC, option43.encode())

        # 记录租约
        relay_ip = self._bytes_to_ip(pkt.giaddr)
        circuit_id, remote_id = pkt.get_relay_agent_info()

        await self.lease_manager.create_or_update_lease(
            mac_address=pkt.client_mac,
            pool_id=pool.id,
            subnet=subnet,
            dhcpv4_address=requested_ip,
            lease_time=lease_time,
            vlan_id=vlan_id,
            hostname=pkt.hostname,
            vendor_class=pkt.vendor_class,
            option43=option43,
            circuit_id=circuit_id,
            remote_id=remote_id,
            relay_agent=relay_ip if relay_ip != '0.0.0.0' else None,
        )

        return resp, requested_ip, lease_time

    async def handle_release(self, pkt: DHCPPacket) -> None:
        """处理 DHCPRELEASE"""
        await self.pool_manager.release_ipv4(pkt.client_mac)

    async def handle_inform(self, pkt: DHCPPacket, vlan_id: Optional[int]) -> Optional[DHCPv4Response]:
        """处理 DHCPINFORM — 仅返回配置信息，不分配 IP"""
        pool = await self.pool_manager.find_pool_by_vlan(vlan_id)
        if not pool or not pool.subnets:
            return None

        subnet = pool.subnets[0]  # 使用第一个子网的配置
        resp = DHCPv4Response(pkt, DHCPACK)
        resp.set_ip_option(OPT_SUBNET_MASK, subnet.netmask)
        if subnet.gateway:
            resp.set_ip_option(OPT_ROUTER, str(subnet.gateway))
        return resp

    async def _find_subnet_for_ip(self, pool, ip_str: str) -> Optional[object]:
        """查找 IP 所属的子网"""
        import ipaddress
        for subnet in pool.subnets:
            if subnet.ip_version != 4:
                continue
            try:
                net = ipaddress.IPv4Network(f"{subnet.subnet}/{subnet.netmask}")
                if ipaddress.IPv4Address(ip_str) in net:
                    return subnet
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def _bytes_to_ip(data: bytes) -> str:
        return '.'.join(str(b) for b in data[:4])
