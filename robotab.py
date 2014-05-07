from random import choice

import uwsgi
import redis
import math3d
from gevent import Greenlet, select, sleep


class Arena(object):

    def __init__(self, max_players=5, warmup=30):
        self.greenlets = {'engine': self.engine_start, 'start': self.start}
        self.animations = []
        self.players = {}
        self.waiting_players = {}
        self.max_players = max_players
        self.warmup = warmup
        self.warming_up = False

        self.arena = "arena{}".format(uwsgi.worker_id())
        self.redis = redis.StrictRedis()
        self.channel = redis.pubsub()
        self.channel.subscribe(self.arena)

        self.bonus_malus_queue = ['haste', 'giant', 'heal', 'power']

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

    def cmd_handler(self, player, cmd):
        if cmd == 'rl':
            player.math.rotateY(0.2)
            return True

        if cmd == 'rr':
            player.math.rotateY(-0.2)
            return True

        if cmd == 'fw':
            old = player.math.position_tuple()
            player.math.translateZ(15)
            if (self.collision(player)):
                player.math.set_position(old)
                player.math.translateZ(-60)
            return True

        if cmd == 'bw':
            old = player.math.position_tuple()
            player.math.translateZ(-15)
            if (self.collision(player)):
                player.math.set_position(old)
                player.math.translateZ(60)
            return True

        return False

    def collision(self, player):
        for p in self.players.keys():
            if self.players[p] == player:
                continue
            #check for body collision
            if player.math.circleCollide(self.players[p].math.position.x,
                                         self.players[p].math.position.z,
                                         self.players[p].math.radius * self.players[p].math.scale):
                if player.attack == 1:
                    if self.players[p].attack == 0:
                        self.players[p].energy -= 1.0
                    else:
                        self.players[p].energy -= 0.1
                elif self.players[p]. attack == 1:
                    player.energy -= 1.0
                self.broadcast("bm,collision between {} and {}".format(player.name, p))
                return True
            return False

    def engine_start(self):
        del self.channel.greenlets['engine']
        print('engine started')
        while True:
            if len(self.players) == 0:
                break
            t = uwsgi.micros() / 1000.0
            for p in self.players.keys():
                player = self.players[p]
                if player.cmd:
                    draw = self.cmd_handler(player, player.cmd)
                    if draw:
                        player.update_gfx()
                    player.cmd = None
                if player.attack_cmd:
                    draw = self.attack_cmd_handler(player, player.cmd)
                    if draw:
                        player.update_gfx()
                    player.attack_cmd = None
            for animation in self.animations:
                animation.animate()
            t1 = uwsgi.micros() / 1000.0
            delta = t1 - t
            if delta < 33.33:
                sleep((33.33 - delta) / 1000.0)

        self.channel.greenlets['engine'] = self.engine_start
        print("engine ended")

    def start(self):
        del self.greenlets['start']
        self.warming_up = True
        warmup = self.warmup
        while warmup > 0:
            sleep(1.0)
            self.broadcast("warmup,{} seconds to start".format(warmup))
            warmup -= 1
            print(warmup)
        self.warmup = False
        print('FIGHT!!!')
        sleep()
        self.started = True
        sleep()
        self.broadcast("FIGHT!!!")
        # this queue is initialized on game startup
        # with a random list of bonus/malus items to drop on the arena
        # it is consumed every 10 seconds
        # consume bonus_malus_queue
        for el in range(5):
            sleep(3.0)
            self.broadcast("bm,{}".format(choice(self.bonus_malus_queue)))
        sleep(1.0)
        self.broadcast("end")
        self.started = False
        self.greenlets['start'] = self.start
        sleep()


def wait_for_game():
    while True:
        sleep(1)


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

        self.math = math3d.MathPlayer(0.0, 50, 0.0)
        self.math.translateZ(-580)
        self.math.translateX(-580)

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
        del self.game.players[self.name]

    def send_all(self, msg):
        self.redis.publish(self.arena, msg)

    def update_gfx(self):
        msg = "{}:{},{},{},{},{},{}".format(self.name, self.math.rotation.y, self.math.position.x, self.math.position.y, self.math.position.z, self.attack, self.energy)
        self.send_all(msg)


class Bullet(object):

    def __init__(self, game, player, _range=1000.0):
        self.game = game
        self.math = math3d.MathPlayer(0.0, 50, 0.0)
        self.player = player
        self.is_shooting = 0
        self._range = _range

    def shoot(self):
        if self.is_shooting > 0:
            return
        self.math.position.x = self.player.math.position.x
        self.math.position.y = self.player.math.position.y
        self.math.position.z = self.player.math.position.z
        self.math.rotation.y = self.player.math.rotation.y
        self.is_shooting = self._range
        self.player.energy -= 0.1
        self.game.animations.append(self)

    def animate(self):
        self.math.translateZ(50)
        if self.collision():
            self.is_shooting = 0
        else:
            self.is_shooting -= 50
        msg = "!{}:{},{},{},{},{}".format(self.player.name, self.math.rotation.y, self.math.position.x, self.math.position.y, self.math.position.z, self.is_shooting)
        self.player.send_all(msg)
        if self.is_shooting <= 0:
            self.game.animations.remove(self)

    def collision(self):
        for p in self.game.players.keys():
            if self.game.players[p] == self.player:
                continue

            if self.math.circleCollide(self.game.players[p].math.position.x,
                                       self.game.players[p].math.position.z,
                                       self.game.players[p].math.radius * self.game.players[p.math.scale]):
                self.game.players[p].energy -= 10.0
                self.game.players[p].update_gfx()
                return True

        return False


class Robotab(Arena):

    def __call__(self, e, sr):
        if e['PATH_INFO'] != '/robotab':
            raise Exception("only /robotab is allowed")
        uwsgi.websocket_handshake()

        player = Player(self, e['QUERY_STRING'], uwsgi.connection_fd())
        self.players[player.name] = player

        for greenlet in self.greenlets:
            if greenlet != 'start' or len(self.players > 1):
                Greenlet.spawn(self.greenlets[greenlet])
            else:
                self.waiting_players[player.name] = player
                print("hey {}, game already started, waiting for next one...".format(player.name))
                wait_for_game()

        player.update_gfx()
        # ?!?!?!?!?!?!?!?!!?!?!?!??!?!
        for p in self.players.keys():
            if self.players[p] != player:
                self.players[p].update_gfx()
        # !?!??!?!?!?!?!?!?!??!?!?!?!?!

        while True:
            ready = select.select([player.fd, player.redis_fd], [], [], timeout=4.0)

            # ?!?!?!?!?!?!?!?!!?!?!?!??!?!
            if not ready[0]:
                uwsgi.websocket_recv_nb()
            # ?!?!?!?!?!?!?!?!!?!?!?!??!?!

            for fd in ready[0]:
                if fd == player.fd:
                    # ?!?!?!?!?!?!?!?!!?!?!?!??!?!
                    try:
                        msg = uwsgi.websocket_recv_nb()
                    except IOError:
                        import sys
                        print sys.exc_info()
                        player.end()
                        return [""]
                    # ?!?!?!?!?!?!?!?!!?!?!?!??!?!
                    if msg:
                        self.msg_handler(player, msg)
                elif fd == player.redis_fd:
                    msg = player.channel.parse_response()
                    if msg[0] == 'message':
                        uwsgi.websocket_send(msg[2])


application = Robotab()
