#!/usr/bin/env python3
# encoding: utf-8

import socket
import os
import time
import binascii

from bencoder import bencode, bdecode
from random import randint
from socket import inet_ntoa
from struct import unpack
from hashlib import sha1


TID_LENGTH = 2

# 索引节点树
BOOTSTRAP_NODES = (
    ("router.bittorrent.com", 6881),
    ("dht.transmissionbt.com", 6881),
    ("router.utorrent.com", 6881),
)

def proper_infohash(infohash):
    if isinstance(infohash, bytes):
        # Convert bytes to hex
        infohash = binascii.hexlify(infohash).decode('utf-8')
    return infohash.upper()

def entropy(length):
    str = ""
    for _ in range(length):
        str += chr(randint(0, 255))
    return str

def random_node_id(size=20):
    return os.urandom(size)

def split_nodes(nodes):
    length = len(nodes)
    if (length % 26) != 0:
        return

    for i in range(0, length, 26):
        nid = nodes[i:i+20]
        ip = inet_ntoa(nodes[i+20:i+24])
        port = unpack("!H", nodes[i+24:i+26])[0]
        yield nid, ip, port

class DHT(object):
    # 模型 修改
    def __init__(self, bind_ip='0.0.0.0', bind_port=333):
        try:
            self.transport = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.transport.settimeout(20)
            self.transport.bind((bind_ip, bind_port))
        except Exception as e:
            print("error: socket - %s" %(e))
            pass

        self.node_id = random_node_id()
        self.ROUTE_NODES = {}
        self.BLACK_IP = {}

    def send_krpc(self, msg, address):
        # print(address, msg['q'])
        # print(msg)
        # print(bencode(msg))
        try:
            self.transport.sendto(bencode(msg), address)
        except Exception as e:
            print(address, e)

    def send_find_node(self, address, node_id=None, target=None):
        self.send_krpc({
            "t": b"fn",
            "y": "q",
            "q": "find_node",
            "a": {
                "id": node_id or random_node_id(),
                "target": target or random_node_id()
            }
        }, address)

    def fake_node_id(self, node_id=None):
        if node_id:
            return node_id[:-1]+self.node_id[-1:]
        return self.node_id

    def send_ping(self, address, node_id=None):
        self.send_krpc({
            "y": "q",
            "t": entropy(2),
            "q": "ping",
            "a": {
                "id": node_id or random_node_id()
            }
        }, address)

    def random_id(self):
        str = entropy(20).encode('latin1')
        return sha1(str).digest()

    def join_dht_network(self):
        print("当前节点数:%s" % (len(self.ROUTE_NODES)))

        num = 3 # 容错次数

        if len(self.ROUTE_NODES) < 8:
            for address in BOOTSTRAP_NODES:
                self.send_find_node(address=address)

        for address in self.ROUTE_NODES:
            if self.ROUTE_NODES[address] > num:
                self.ROUTE_NODES.pop(address)
            else:
                self.send_find_node(address=address)

    def handle_message(self, msg, address):
        if b"y" in msg:
            if msg[b"y"] == b"r": return self.handle_response(msg, address)
            if msg[b"y"] == b'q': return self.handle_query(msg, address=address)
        elif b"e" in msg:
            # 返回错误信息处理 目前处理方式是不处理
            print("错误信息")
            return
        else:
            print("意料之外的结果")
            # 意料之外的结果 暂不处理
            return

    def run(self):
        self.join_dht_network()
        count = 0

        while True:
            try:
                (data, address) = self.transport.recvfrom(65536)
            except:
                if count > 8:
                    count = 0
                    self.join_dht_network()
                else:
                    count += 1
                continue

            try:
                msg = bdecode(data)
            except Exception:
                msg = None
                print('编码解析错误:', data.decode('latin1'))

            if msg:
                self.handle_message(msg, address)


    def handle_query(self,msg, address):
        args = msg[b"a"]
        node_id = args[b"id"]
        query_type = msg[b"q"]

        print("query_type:%s" %(query_type))

        if b"info_hash" in args:
            print("info_hash:%s" %(args[b"info_hash"]))
            return

        if query_type == b"get_peers":
            infohash = args[b"info_hash"]
            infohash = proper_infohash(infohash)
            token = infohash[:2]
            self.send_krpc({
                "t": msg[b"t"],
                "y": "r",
                "r": {
                    "id": self.fake_node_id(node_id),
                    "nodes": "",
                    "token": token
                }
            }, address)
            return self.handle_get_peers(infohash, address)
        elif query_type == b"announce_peer":
            infohash = args[b"info_hash"]
            tid = msg[b"t"]
            self.send_krpc({
                "t": tid,
                "y": "r",
                "r": {
                    "id": self.fake_node_id(node_id)
                }
            }, address)
            peer_addr = [address[0], address[1]]
            try:
                peer_addr[1] = args[b"port"]
            except KeyError:
                pass
            return self.handle_announce_peer(proper_infohash(infohash), address, peer_addr)
        elif query_type == b"find_node":
            # 搜节点这部分 我决定不返回值
            return
            tid = msg[b"t"]
            self.send_krpc({
                "t": tid,
                "y": "r",
                "r": {
                    "id": self.fake_node_id(node_id),
                    "nodes": ""
                }
            }, address)
        elif query_type == b"ping":
            self.send_krpc({
                "t": b"tt",
                "y": "r",
                "r": {
                    # "id": self.fake_node_id(node_id)
                    "id": self.node_id
                }
            }, address)
        # self.send_find_node(address, node_id)

    def handle_response(self, msg, address):
        args = msg[b"r"]
        if b"nodes" in args:
            # 这里如果等于说名是find_node回来的数据 否则就是ping返回的

            # 超时次数统计
            if address in self.ROUTE_NODES:
                if self.ROUTE_NODES[address] > 0:
                    self.ROUTE_NODES[address] -= 1
            else:
                self.ROUTE_NODES[address] = 0

            ipTemp = None
            for node_id, ip, port in split_nodes(args[b"nodes"]):
                if ipTemp == ip:
                    break
                elif (ip, port) == address:
                    # 像这种应该被拉入节点黑名单
                    break
                else:
                    ipTemp = ip
                    # self.send_ping((ip, port))
                    self.send_find_node((ip, port))


if __name__ == "__main__":
    server = DHT()
    server.run()
