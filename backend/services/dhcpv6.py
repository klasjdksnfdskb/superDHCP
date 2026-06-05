"""
DHCPv6 协议引擎 — RFC 8415 / RFC 3315

处理 DHCPv6 协议消息:
- SOLICIT    → ADVERTISE  (类似 v4 DISCOVER/OFFER)
- REQUEST    → REPLY      (类似 v4 REQUEST/ACK)
- RENEW      → REPLY      (续租)
- REBIND     → REPLY      (重绑定)
- RELEASE    → REPLY      (释放)
- DECLINE    → REPLY      (拒绝)
- CONFIRM    → REPLY      (确认)
- INFORMATION-REQUEST → REPLY (无状态信息请求)

支持:
- DUID (客户端唯一标识): DUID-LLT / DUID-EN / DUID-LL
- IA_NA (非临时地址关联): 有状态地址分配
- IA_TA (临时地址关联)
- IA_PD (前缀委派)
- Option 16 (Vendor Class)
- Option 17 (Vendor-specific Information)
"""

import struct
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ─── DHCPv6 常量 ───
DHCPV6_SERVER_PORT = 547
DHCPV6_CLIENT_PORT = 546

# 消息类型
SOLICIT = 1
ADVERTISE = 2
REQUEST = 3
CONFIRM = 4
RENEW = 5
REBIND = 6
REPLY = 7
RELEASE = 8
DECLINE = 9
RECONFIGURE = 10
INFORMATION_REQUEST = 11
RELAY_FORW = 12
RELAY_REPL = 13

# Option 代码
OPT_CLIENTID = 1
OPT_SERVERID = 2
OPT_IA_NA = 3
OPT_IA_TA = 4
OPT_IAADDR = 5
OPT_ORO = 6        # Option Request Option
OPT_PREFERENCE = 7
OPT_ELAPSED_TIME = 8
OPT_RELAY_MSG = 9
OPT_STATUS_CODE = 13
OPT_RAPID_COMMIT = 14
OPT_USER_CLASS = 15
OPT_VENDOR_CLASS = 16
OPT_VENDOR_OPTS = 17
OPT_INTERFACE_ID = 18
OPT_RECONF_MSG = 19
OPT_RECONF_ACCEPT = 20
OPT_DNS_SERVERS = 23
OPT_DOMAIN_LIST = 24
OPT_IA_PD = 25
OPT_IAPREFIX = 26

# DUID 类型
DUID_LLT = 1   # Link-layer + Time
DUID_EN = 2    # Enterprise Number
DUID_LL = 3    # Link-layer
DUID_UUID = 4  # UUID-based

# 状态码
STATUS_SUCCESS = 0
STATUS_UNSPEC_FAIL = 1
STATUS_NO_ADDRS_AVAIL = 2
STATUS_NO_BINDING = 3
STATUS_NOT_ON_LINK = 4
STATUS_USE_MULTICAST = 5
STATUS_NO_PREFIX_AVAIL = 6


class DHCPv6Packet:
    """DHCPv6 报文解析"""

    def __init__(self, data: bytes):
        self.raw = data
        self.msg_type = data[0]
        self.transaction_id = data[1:4]
        self.options: Dict[int, List[Tuple[int, bytes]]] = {}

        self._parse_options(data[4:])
        self.client_duid = self._get_option_value(OPT_CLIENTID)
        self.server_duid = self._get_option_value(OPT_SERVERID)
        self.ia_na = self._get_option_value(OPT_IA_NA)  # IA_NA raw
        self.oro = self._parse_oro()
        self.vendor_class = self._get_option_value(OPT_VENDOR_CLASS)

    def _parse_options(self, data: bytes):
        pos = 0
        while pos + 4 <= len(data):
            code = struct.unpack('!H', data[pos:pos+2])[0]
            length = struct.unpack('!H', data[pos+2:pos+4])[0]
            pos += 4
            if pos + length > len(data):
                break
            value = data[pos:pos+length]
            if code not in self.options:
                self.options[code] = []
            self.options[code].append((length, value))
            pos += length

    def _get_option_value(self, code: int) -> Optional[bytes]:
        items = self.options.get(code, [])
        return items[0][1] if items else None

    def _parse_oro(self) -> List[int]:
        """解析 Option Request Option"""
        data = self._get_option_value(OPT_ORO)
        if not data:
            return []
        return [struct.unpack('!H', data[i:i+2])[0]
                for i in range(0, len(data), 2)]

    def parse_duid(self) -> Dict:
        """解析 DUID 结构"""
        duid_data = self.client_duid
        if not duid_data or len(duid_data) < 4:
            return {"raw": duid_data.hex() if duid_data else ""}

        duid_type = struct.unpack('!H', duid_data[0:2])[0]
        result = {"type": duid_type, "type_name": self._duid_type_name(duid_type)}

        if duid_type == DUID_LLT and len(duid_data) >= 8:
            hw_type = struct.unpack('!H', duid_data[2:4])[0]
            timestamp = struct.unpack('!I', duid_data[4:8])[0]
            link_addr = duid_data[8:]
            result["hw_type"] = hw_type
            result["timestamp"] = timestamp
            result["link_addr"] = ':'.join(f'{b:02x}' for b in link_addr)

        elif duid_type == DUID_EN and len(duid_data) >= 8:
            enterprise_num = struct.unpack('!I', duid_data[2:6])[0]
            identifier = duid_data[6:]
            result["enterprise_number"] = enterprise_num
            result["identifier"] = identifier.hex()

        elif duid_type == DUID_LL and len(duid_data) >= 4:
            hw_type = struct.unpack('!H', duid_data[2:4])[0]
            link_addr = duid_data[4:]
            result["hw_type"] = hw_type
            result["link_addr"] = ':'.join(f'{b:02x}' for b in link_addr)

        result["raw"] = duid_data.hex()
        return result

    @staticmethod
    def _duid_type_name(t: int) -> str:
        return {1: "DUID-LLT", 2: "DUID-EN", 3: "DUID-LL", 4: "DUID-UUID"}.get(t, f"Unknown({t})")

    def parse_iana(self) -> Tuple[Optional[int], Optional[int], List[str]]:
        """解析 IA_NA (Identity Association for Non-temporary Addresses)"""
        data = self.ia_na
        if not data or len(data) < 12:
            return None, None, []

        iaid = struct.unpack('!I', data[0:4])[0]
        t1 = struct.unpack('!I', data[4:8])[0]
        t2 = struct.unpack('!I', data[8:12])[0]

        addresses = []
        pos = 12
        while pos + 4 <= len(data):
            opt_code = struct.unpack('!H', data[pos:pos+2])[0]
            opt_len = struct.unpack('!H', data[pos+2:pos+4])[0]
            pos += 4
            if opt_code == OPT_IAADDR and opt_len >= 24:
                addr = data[pos:pos+16]
                pref_life = struct.unpack('!I', data[pos+16:pos+20])[0]
                valid_life = struct.unpack('!I', data[pos+20:pos+24])[0]
                addr_str = ':'.join(f'{addr[i*2]:02x}{addr[i*2+1]:02x}'
                                    for i in range(8))
                addresses.append(addr_str)
            pos += opt_len

        return iaid, t1, addresses

    def extract_mac_from_duid(self) -> Optional[str]:
        """从 DUID-LL 或 DUID-LLT 中提取 MAC 地址"""
        duid_data = self.client_duid
        if not duid_data or len(duid_data) < 4:
            return None

        duid_type = struct.unpack('!H', duid_data[0:2])[0]

        if duid_type == DUID_LLT and len(duid_data) >= 14:
            return ':'.join(f'{b:02x}' for b in duid_data[8:14])
        elif duid_type == DUID_LL and len(duid_data) >= 10:
            return ':'.join(f'{b:02x}' for b in duid_data[4:10])

        return None

    def parse_iapd(self) -> Tuple[Optional[int], Optional[int], int]:
        """
        解析 IA_PD (Identity Association for Prefix Delegation)
        返回: (iaid, t1, requested_prefix_len)
        """
        data = None
        for code in (OPT_IA_PD,):
            items = self.options.get(code, [])
            if items:
                data = items[0][1]
                break
        if not data or len(data) < 12:
            return None, None, 0

        iaid = struct.unpack('!I', data[0:4])[0]
        t1 = struct.unpack('!I', data[4:8])[0]
        t2 = struct.unpack('!I', data[8:12])[0]

        # 解析 IAPREFIX 子选项
        requested_len = 0
        pos = 12
        while pos + 4 <= len(data):
            opt_code = struct.unpack('!H', data[pos:pos+2])[0]
            opt_len = struct.unpack('!H', data[pos+2:pos+4])[0]
            pos += 4
            if opt_code == OPT_IAPREFIX and opt_len >= 25:
                pref_life = struct.unpack('!I', data[pos:pos+4])[0]
                valid_life = struct.unpack('!I', data[pos+4:pos+8])[0]
                prefix_len = data[pos+8]
                requested_len = prefix_len
            pos += opt_len

        return iaid, t1, requested_len


class DHCPv6Response:
    """构建 DHCPv6 响应报文"""

    def __init__(self, request: DHCPv6Packet, msg_type: int):
        self.request = request
        self.msg_type = msg_type
        self.options: Dict[int, bytes] = {}

    def set_option(self, code: int, value: bytes):
        self.options[code] = value

    def build(self) -> bytes:
        """构建完整 DHCPv6 响应报文"""
        pkt = bytearray()
        pkt.append(self.msg_type)
        pkt.extend(self.request.transaction_id)

        for code, value in sorted(self.options.items()):
            pkt.extend(struct.pack('!HH', code, len(value)))
            pkt.extend(value)

        return bytes(pkt)


class DHCPv6Engine:
    """
    DHCPv6 协议处理引擎
    
    支持两种模式:
    - 有状态 (Stateful): 服务器分配并管理 IPv6 地址 (类似 v4 DHCP)
    - 无状态 (Stateless): 仅提供 DNS/域名等配置信息，地址由 SLAAC 生成
    """

    def __init__(self, pool_manager, lease_manager):
        self.pool_manager = pool_manager
        self.lease_manager = lease_manager
        self.server_duid = self._generate_duid()

    @staticmethod
    def _generate_duid() -> bytes:
        """
        生成 Server DUID (DUID-LLT)
        结构: type(2B) + hw_type(2B) + timestamp(4B) + mac(6B)
        使用随机 MAC + 当前时间戳
        """
        import time
        import random
        import uuid

        duid = bytearray()
        duid.extend(struct.pack('!H', DUID_LLT))  # DUID-LLT
        duid.extend(struct.pack('!H', 1))          # Ethernet
        duid.extend(struct.pack('!I', int(time.time())))

        # 使用系统第一个可用 MAC 或随机生成
        mac = uuid.getnode()
        mac_bytes = struct.pack('!Q', mac)[2:]  # 后 6 字节
        duid.extend(mac_bytes)

        logger.info(f"Server DUID: {duid.hex()}")
        return bytes(duid)

    async def handle_solicit(self, pkt: DHCPv6Packet, vlan_id: Optional[int],
                             client_mac: Optional[str] = None) -> Tuple[Optional[DHCPv6Response], Optional[str], Optional[str]]:
        """
        处理 SOLICIT → ADVERTISE

        返回: (response, assigned_address, mode)
        mode: "stateful" | "stateless" | "pd"
        """
        pool = await self.pool_manager.find_pool_by_vlan(vlan_id)
        if not pool:
            logger.warning(f"DHCPv6 SOLICIT: VLAN={vlan_id} 无匹配地址池")
            return None, None, None

        duid_info = pkt.parse_duid()
        duid_hex = duid_info.get("raw", "")

        # 检查是否请求 IA_PD (前缀委派)
        iaid_pd, t1_pd, prefix_len = pkt.parse_iapd()
        if iaid_pd is not None and prefix_len > 0:
            pd_result = await self._handle_pd(pool, pkt, duid_hex, iaid_pd, t1_pd, prefix_len)
            if pd_result:
                return pd_result

        # 尝试有状态地址分配
        ipv6_addr = await self.pool_manager.allocate_ipv6(pool.id, client_mac or duid_hex)
        if ipv6_addr:
            resp = DHCPv6Response(pkt, ADVERTISE)
            self._add_server_id(resp)
            self._add_client_id(resp, pkt)
            self._add_iana_response(resp, pkt, ipv6_addr)
            return resp, ipv6_addr, "stateful"

        # 无状态模式 — 只提供配置信息
        logger.info(f"DHCPv6 SOLICIT: 使用无状态模式响应")
        resp = DHCPv6Response(pkt, ADVERTISE)
        self._add_server_id(resp)
        self._add_client_id(resp, pkt)
        return resp, None, "stateless"

    async def handle_request(self, pkt: DHCPv6Packet, vlan_id: Optional[int],
                             client_mac: Optional[str] = None) -> Tuple[Optional[DHCPv6Response], Optional[str], Optional[str]]:
        """
        处理 REQUEST → REPLY

        有状态: 确认地址分配
        前缀委派(PD): 确认前缀
        无状态: 返回配置信息
        """
        pool = await self.pool_manager.find_pool_by_vlan(vlan_id)
        if not pool:
            return DHCPv6Response(pkt, REPLY), None, None

        duid_info = pkt.parse_duid()
        duid_hex = duid_info.get("raw", "")
        iaid, t1, requested_addrs = pkt.parse_iana()

        # 检查 IA_PD (前缀委派确认)
        iaid_pd, t1_pd, prefix_len = pkt.parse_iapd()
        if iaid_pd is not None and prefix_len > 0:
            pd_result = await self._handle_pd(pool, pkt, duid_hex, iaid_pd, t1_pd, prefix_len, is_request=True)
            if pd_result:
                return pd_result

        if requested_addrs:
            # 有状态模式
            ipv6_addr = requested_addrs[0]
            resp = DHCPv6Response(pkt, REPLY)
            self._add_server_id(resp)
            self._add_client_id(resp, pkt)
            self._add_iana_response(resp, pkt, ipv6_addr)

            # 记录租约
            subnet = await self._find_subnet_for_ipv6(pool, ipv6_addr)
            lease_time = subnet.lease_time if subnet else 86400

            await self.lease_manager.update_dhcpv6_lease(
                mac_address=client_mac,
                duid=duid_hex,
                iaid=iaid,
                dhcpv6_address=ipv6_addr,
                lease_time=lease_time,
                mode="stateful",
                pool_id=pool.id,
            )

            return resp, ipv6_addr, "stateful"

        # 无状态模式
        resp = DHCPv6Response(pkt, REPLY)
        self._add_server_id(resp)
        self._add_client_id(resp, pkt)
        self._add_stateless_options(resp, pkt, pool)
        return resp, None, "stateless"

    async def handle_information_request(self, pkt: DHCPv6Packet, vlan_id: Optional[int],
                                         client_mac: Optional[str] = None) -> Optional[DHCPv6Response]:
        """
        处理 INFORMATION-REQUEST → REPLY (无状态模式)
        
        客户端使用 SLAAC 获取地址，通过此请求获取 DNS/域名等配置
        """
        pool = await self.pool_manager.find_pool_by_vlan(vlan_id)
        if not pool:
            return None

        resp = DHCPv6Response(pkt, REPLY)
        self._add_server_id(resp)
        self._add_client_id(resp, pkt)
        self._add_stateless_options(resp, pkt, pool)

        # 记录无状态租约
        duid_info = pkt.parse_duid()
        duid_hex = duid_info.get("raw", "")

        await self.lease_manager.update_dhcpv6_stateless(
            mac_address=client_mac,
            duid=duid_hex,
            pool_id=pool.id,
        )

        return resp

    async def handle_renew(self, pkt: DHCPv6Packet, client_mac: Optional[str] = None) -> Optional[DHCPv6Response]:
        """处理 RENEW → REPLY (续租)"""
        duid_info = pkt.parse_duid()
        duid_hex = duid_info.get("raw", "")
        iaid, t1, addresses = pkt.parse_iana()

        resp = DHCPv6Response(pkt, REPLY)
        self._add_server_id(resp)
        self._add_client_id(resp, pkt)

        if addresses:
            self._add_iana_response(resp, pkt, addresses[0])
            # 更新租约
            await self.lease_manager.renew_dhcpv6(client_mac, duid_hex, addresses[0])

        return resp

    async def handle_release(self, pkt: DHCPv6Packet, client_mac: Optional[str] = None) -> Optional[DHCPv6Response]:
        """处理 RELEASE → REPLY"""
        resp = DHCPv6Response(pkt, REPLY)
        self._add_server_id(resp)
        self._add_client_id(resp, pkt)
        self._add_status_code(resp, STATUS_SUCCESS, "Released")

        duid_info = pkt.parse_duid()
        await self.lease_manager.release_dhcpv6(client_mac, duid_info.get("raw", ""))

        return resp

    # ─── Helper Methods ───

    async def _handle_pd(self, pool, pkt: DHCPv6Packet, duid_hex: str,
                         iaid: int, t1: Optional[int], prefix_len: int,
                         is_request: bool = False) -> Optional[Tuple[DHCPv6Response, str, str]]:
        """
        处理前缀委派 (Prefix Delegation)

        策略:
        1. 查找 pool 中 v6_mode='pd' 的子网
        2. 使用 delegation_prefix 作为委派前缀
        3. 若无 PD 子网，回退到 IPv6 状态分配
        """
        # 查找 PD 模式子网
        pd_subnet = None
        for sn in pool.subnets:
            if sn.ip_version == 6 and sn.v6_mode == 'pd' and sn.delegation_prefix:
                pd_subnet = sn
                break

        if not pd_subnet:
            logger.warning(f"DHCPv6 PD: 地址池 {pool.name} 无 PD 子网")
            return None

        delegated_prefix = pd_subnet.delegation_prefix

        # 构建响应
        msg_type = REPLY if is_request else ADVERTISE
        resp = DHCPv6Response(pkt, msg_type)
        self._add_server_id(resp)
        self._add_client_id(resp, pkt)
        self._add_iapd_response(resp, iaid, t1 or 3600, delegated_prefix, prefix_len)
        self._add_stateless_options(resp, pkt, pool)

        # 记录 PD 租约
        if is_request:
            await self.lease_manager.update_dhcpv6_lease(
                mac_address=None,
                duid=duid_hex,
                iaid=iaid,
                dhcpv6_address=delegated_prefix,
                lease_time=86400,
                mode="pd",
                pool_id=pool.id,
            )

        logger.info(f"DHCPv6 PD: 委派前缀 {delegated_prefix}/{prefix_len} → DUID={duid_hex[:16]}...")
        return resp, f"{delegated_prefix}/{prefix_len}", "pd"

    def _add_iapd_response(self, resp: DHCPv6Response, iaid: int, t1: int,
                           prefix: str, prefix_len: int):
        """构建 IA_PD 响应 (含 IAPREFIX)"""
        t2 = int(t1 * 0.8)
        pref_life = 3600
        valid_life = 7200

        # 解析委派前缀为 IPv6 字节
        prefix_net = prefix
        if '/' in prefix_net:
            prefix_net = prefix_net.split('/')[0]

        try:
            import ipaddress
            prefix_bytes = ipaddress.IPv6Network(f"{prefix_net}/{prefix_len}", strict=False).network_address.packed
        except Exception:
            # fallback: 用零填充
            prefix_bytes = bytes(16)

        # IAPREFIX 子选项 (25 bytes minimum)
        iaprefix = struct.pack('!HH', OPT_IAPREFIX, 25)
        iaprefix += struct.pack('!II', pref_life, valid_life)
        iaprefix += struct.pack('!B', prefix_len)
        iaprefix += prefix_bytes

        # IA_PD option
        iapd = struct.pack('!IIII', iaid, t1, t2, 0)
        iapd += iaprefix

        resp.set_option(OPT_IA_PD, iapd)

    def _add_server_id(self, resp: DHCPv6Response):
        resp.set_option(OPT_SERVERID, self.server_duid)

    def _add_client_id(self, resp: DHCPv6Response, pkt: DHCPv6Packet):
        if pkt.client_duid:
            resp.set_option(OPT_CLIENTID, pkt.client_duid)

    def _add_status_code(self, resp: DHCPv6Response, code: int, message: str = ""):
        msg_bytes = message.encode('utf-8')
        resp.set_option(OPT_STATUS_CODE, struct.pack('!H', code) + msg_bytes)

    def _add_iana_response(self, resp: DHCPv6Response, pkt: DHCPv6Packet, address: str):
        """构建 IA_NA 响应 (含 IAADDR)"""
        iaid, t1, _ = pkt.parse_iana()
        if iaid is None:
            return

        t1 = t1 or 3600
        t2 = int(t1 * 0.8)

        # 构造 IPv6 地址二进制
        parts = address.split(':')
        addr_bytes = bytes(int(p, 16) for p in address.replace('::', ':0:').split(':')[-8:])

        # 需要规范化 IPv6 地址
        try:
            import ipaddress
            addr_bytes = ipaddress.IPv6Address(address).packed
        except Exception:
            pass

        # IAADDR option
        iaaddr = struct.pack('!HH', OPT_IAADDR, 24)  # 24 = 16B addr + 4B pref + 4B valid
        iaaddr += addr_bytes
        iaaddr += struct.pack('!II', 3600, 7200)  # preferred/valid lifetime

        # IA_NA option
        iana = struct.pack('!IIII', iaid, t1, t2, 0)  # T1, T2, IAID
        iana += iaaddr

        resp.set_option(OPT_IA_NA, iana)

    def _add_stateless_options(self, resp: DHCPv6Response, pkt: DHCPv6Packet, pool):
        """添加无状态配置选项 (DNS/域名等)"""
        # DNS 服务器
        if pool.subnets:
            subnet = pool.subnets[0]
            if subnet.dns_servers:
                dns_bytes = bytearray()
                for dns in subnet.dns_servers:
                    try:
                        import ipaddress
                        dns_bytes.extend(ipaddress.IPv6Address(str(dns)).packed)
                    except Exception:
                        continue
                if dns_bytes:
                    resp.set_option(OPT_DNS_SERVERS, bytes(dns_bytes))

        # 域名搜索列表
        if pool.domain_name:
            resp.set_option(
                OPT_DOMAIN_LIST,
                pool.domain_name.encode('utf-8')
            )

    @staticmethod
    async def _find_subnet_for_ipv6(pool, ip_str: str):
        import ipaddress
        for subnet in pool.subnets:
            if subnet.ip_version != 6:
                continue
            try:
                net = ipaddress.IPv6Network(f"{subnet.subnet}/{subnet.netmask}")
                if ipaddress.IPv6Address(ip_str) in net:
                    return subnet
            except (ValueError, TypeError):
                continue
        return None
