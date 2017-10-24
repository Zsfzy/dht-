from maga import Maga

import libtorrent as lt
import logging
import os.path as op
import time

logging.basicConfig(level=logging.INFO)

# magnet:?xt=urn: + infohash = 磁力链接
# magnet:?xt=urn:btih:

runPath = op.split(op.realpath(__file__))[0]

def infohash_to_torrent(infohash):
    ses = lt.session()
    ses.add_dht_router('router.bittorrent.com', 6881)
    ses.add_dht_router('router.utorrent.com', 6881)
    ses.add_dht_router('router.bitcomet.com', 6881)
    ses.add_dht_router('dht.transmissionbt.com', 6881)
    ses.start_dht();

    params = {
        'save_path': runPath + '/torrent',
        'storage_mode': lt.storage_mode_t(2),
        # 'storage_mode': lt.storage_mode_t.storage_mode_sparse,
        'paused': False,
        'auto_managed': True,
        'duplicate_is_error': True
    }
    handle = lt.add_magnet_uri(ses, 'magnet:?xt=urn:btih:' + infohash, params)

    while (not handle.has_metadata()):
        time.sleep(1)
        # print('下载中')
    ses.pause()
    print('完成')
    torinfo = handle.get_torrent_info()
    torfile = lt.create_torrent(torinfo)

    output = op.abspath(torinfo.name() + ".torrent")

class torrent(object):
    pass


class Crawler(Maga):
     async def handler(self, infohash, addr):
        logging.info(addr)
        logging.info(infohash)
        infohash_to_torrent(infohash)

# class Crawler(Maga):
#     async def handle_get_peers(self, infohash, addr):
#         logging.info(
#             "Receive get peers message from DHT {}. Infohash: {}.".format(
#                 addr, infohash
#             )
#         )
#
#     async def handle_announce_peer(self, infohash, addr, peer_addr):
#         logging.info(
#             "Receive announce peer message from DHT {}. Infohash: {}. Peer address:{}".format(
#                 addr, infohash, peer_addr
#             )
#         )

crawler = Crawler()
crawler.run(6881)
# infohash_to_torrent('B5489D1B1397F1F2487A8A0851852563B08C70B7')
