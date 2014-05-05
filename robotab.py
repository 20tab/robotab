import uwsgi
import redis
from gevent import Greenlet, select

class Arena(object):

    def __init__(self, max_players=5, warmup=30):
        self.players = {}
        self.waiting_players = {}
        self.max_players = max_players
        self.warmup = warmup
        self.warming_up = False
        self.arena = "arena{}".format(uwsgi.worker_id())
        self.redis = redis.StrictRedis()
        self.channel = redis.pubsub()
        self.channel.subscribe(self.arena)
        self.greenlets = {'engine':self.engine_start, 'start':self.start}

    def broadcast(self, msg):
        self.redis.publish(self.arena, 'arena:{}'.format(msg))

    def msg_handler(self, player, msg):
        p, cmd = msg.split(':')
        if cmd in ('at', 'AT'):
            self.players[p].attack_cmd = cmd
        else:
            self.players[p].cmd = cmd

    def attack_cmd_handler(self, player, cmd):
        if cmd == 'AT':
            player.bullet.shoot()
            player.attack = 1
            return True

        elif cmd == 'at':
            player.attack = 0

        return False

    def engine_start(self):
        def engine(self):


def wait_for_game():
    while True:
        gevent.sleep(1)

# place up to 8 waiting_players
# in the player list and start the game again
# unless less than 2 players are available
def winning_logic():
    pass


class Player(object):
    def __init__(self, game, name, fd):
        self.game = game
        self.name = name
        self.fd = fd
        self.attack = 0
        self.energy = 100.0
        self.arena = "arena{}".format(uwsgi.worker_id())
        self.redis = redis.StrictRedis()
        self.channel = redis.pubsub()
        self.channel.subscribe(self.arena)
        self.redis_fd = self.channel.connection._socket.fileno()
        self.cmd = None
        self.attack_cmd = None
        self.bullet = Bullet(self.game, self)

        # check if self.energy is 0, in such a case
        # trigger the kill procedure removing the player from the list
        # if after the death a single player remains, trigger the winning procedure
        def damage(self, amount):
            pass

    def end(self):
        print("ending...")
        del(self.game.players[self.name])

    def send_all(self, msg):
        self.redis.publish(self.arena, msg)

    def update_gfx(self):
        msg = "{}:{}:{}:{}:{}:{}:{}".format(self.name, self.math.rotation.y, self.math.position.x, self.math.position.y, self.math.position.z, self.attack, self.energy)
        self.send_all(msg)


class Bullet(object):
    def __init__(self, game, player, _range=1000.0):
        self.game = game
        self.player = player
        self.is_shooting = 0
        self._range = _range


class Robotab(Arena):

    def __call__(self, e, sr):
        if e['PATH_INFO'] != '/robotab':
            raise Exception("only /robotab is allowed")
        uwsgi.websocket_handshake()
        print("websockets..")
        player = Player(self, env['QUERY_STRING'], uwsgi.connection_fd())
        self.players[player.name] = player























