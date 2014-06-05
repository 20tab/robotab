from random import choice, randrange

import uwsgi
import gevent
import gevent.queue
import gevent.event
import gevent.select
import redis
import math


class ArenaObject(object):

    def __init__(self, x, y, r, speed=15):
        self.height = 13.5
        self.width = 13.5
        self.scale = 5
        self.x = x
        self.y = y
        self.r = r
        self.speed = speed

    def translate(self, amount):
        amount_x = math.sin(self.r) * amount
        amount_y = math.cos(self.r) * amount
        self.x += round(amount_x)
        self.y += round(amount_y)
        #print('x:{}  y:{}  r:{}'.format(self.x, self.y, self.r))

    def rotateR(self):
        if self.r <= 0:
            self.r = 2 * math.pi
        else:
            self.r -= 0.1

    def rotateL(self):
        if self.r >= 2 * math.pi:
            self.r = 0
        else:
            self.r += 0.1

    def collide(self, x, y, width, height):
        dx = abs(self.x - x) * 2
        dw = self.width * self.scale + width
        dy = abs(self.y - y) * 2
        dh = self.height * self.scale + height
        return (dx < dw) and (dy < dh)


class Bonus(object):

    def __init__(self, game, id, x, y, type):
        self.game = game
        self.id = id
        self.type = type
        self.arena_object = ArenaObject(x, y, 0, 0)
        self.game.active_bonus_malus.append(self)
        self.game.broadcast('bm,{},{},{},{},{}'.format(self.id, self.type, self.arena_object.x, 50, self.arena_object.y))

    def activate_bonus(self, player):
        self.game.active_bonus_malus.remove(self)
        self.game.broadcast('bm,gv,{},{},{}'.format(self.id, self.type, player.name))
        self.game.bonus_malus_spawn_points.append((self.arena_object.x, self.arena_object.y))


class TimerBonus(Bonus):
    def __init__(self, game, id, x, y, type, time=15):
        super(TimerBonus, self).__init__(game, id, x, y, type)
        self.time = time


class BonusHaste(TimerBonus):
    def __init__(self, game, id, x, y, type='haste'):
        super(BonusHaste, self).__init__(game, id, x, y, type)

    def activate_bonus(self, player):
        super(BonusHaste, self).activate_bonus(player)
        old_speed = player.arena_object.speed
        player.arena_object.speed *= 2
        gevent.sleep(self.time)
        player.arena_object.speed = old_speed
        self.game.broadcast('bm,rm,{},{}'.format(self.type, player.name))


class BonusPower(TimerBonus):
    def __init__(self, game, id, x, y, type='power'):
        super(BonusPower, self).__init__(game, id, x, y, type)

    def activate_bonus(self, player):
        super(BonusPower, self).activate_bonus(player)
        old_damage = player.bullet.damage
        player.bullet.damage *= 2
        gevent.sleep(self.time)
        player.bullet.damage = old_damage
        self.game.broadcast('bm,rm,{},{}'.format(self.type, player.name))


class BonusHeal(Bonus):

    def __init__(self, game, id, x, y, type='heal', amount=50.0):
        super(BonusHeal, self).__init__(game, id, x, y, type)
        self.amount = amount

    def activate_bonus(self, player):
        super(BonusHeal, self).activate_bonus(player)
        player.energy = player.energy + self.amount if player.energy <= 50 else 100.0


class Arena(object):

    def __init__(self, min_players=3, max_players=8, warmup=10):
        self.greenlets = {
            'engine': self.engine_start,
            'start': self.start
        }

        self.posters = ['posters/robbo.jpg', 'posters/raffo.jpg', 'posters/unbit.jpg', 'posters/20tab.jpg', 'posters/beri.jpg', 'posters/pycon.jpg']
        self.animations = []
        self.players = {}
        self.waiting_players = []
        self.min_players = min_players
        self.max_players = max_players
        self.warmup = warmup
        self.started = False
        self.finished = False
        #self.warming_up = False
        self.walls = (
            #sc_x,  sc_y,   sc_z,     x,       y,     z,            r
            (200,     100,     50,     0,     150, -1950,            0),
            (200,     100,     50, -1950,     150,     0, -math.pi / 2),
            (200,     100,     50,  1950,     150,     0, -math.pi / 2),
            (200,     100,     50,     0,     150,  1950,            0),

            ( 50,      50,     30,  -730,     150, -1200,            0),
            ( 50,      50,     30,   730,     150, -1200,            0),

            ( 50,      50,     30, -1200,     150,  -730, -math.pi / 2),
            ( 50,      50,     30, -1200,     150,   730, -math.pi / 2),

            ( 50,      50,     30,  1200,     150,  -730, -math.pi / 2),
            ( 50,      50,     30,  1200,     150,   730, -math.pi / 2),

            ( 50,      50,     30,  -730,     150,  1200,            0),
            ( 50,      50,     30,   730,     150,  1200,            0),
        )

        self.spawn_points = (
            #    x,     y,               r
            #(    0,  1650,         math.pi),
            #(    0, -1650,               0),
            ( -935,   935, 3 * math.pi / 4, 0x7777AA),
            (  935,   935, 5 * math.pi / 4, 0x770000),
            (  935,  -935, 7 * math.pi / 4, 0x007700),
            ( -935,  -935,     math.pi / 4, 0x777700),
            (-1650,  1650, 3 * math.pi / 4, 0xAA00AA),
            #(-1650,     0,     math.pi / 2),
            #( 1650,     0, 3 * math.pi / 2),
            ( 1650,  1650, 5 * math.pi / 4, 0x007777),
            ( 1650, -1650, 7 * math.pi / 4, 0x000077),
            (-1650, -1650,     math.pi / 4, 0xFFAA77),

        )

        self.arena = "arena{}".format(uwsgi.worker_id())
        self.redis = redis.StrictRedis()
        self.channel = self.redis.pubsub()
        self.channel.subscribe(self.arena)

        self.bonus_malus = (
            BonusHaste,
            # BonusGiant,
            BonusPower,
            BonusHeal,
        )

        self.bonus_malus_spawn_points = [
            (    0,     0),
            (    0,  1650),
            (    0, -1650),
            (-1650,     0),
            ( 1650,     0),
        ]

        self.active_bonus_malus = []

        self.spawn_iterator = iter(self.spawn_points)

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
            player.arena_object.rotateL()
            return True

        if cmd == 'rr':
            player.arena_object.rotateR()
            return True

        if cmd == 'fw':
            old_x = player.arena_object.x
            old_y = player.arena_object.y
            player.arena_object.translate(player.arena_object.speed)
            if (self.collision(player)):
                player.arena_object.x = old_x
                player.arena_object.y = old_y
                player.arena_object.translate(-player.arena_object.speed)
            return True

        if cmd == 'bw':
            old_x = player.arena_object.x
            old_y = player.arena_object.y
            player.arena_object.translate(-player.arena_object.speed)
            if (self.collision(player)):
                player.arena_object.x = old_x
                player.arena_object.y = old_y
                player.arena_object.translate(player.arena_object.speed)
            return True

        return False

    def collision(self, player):
        for p in self.players.keys():
            if self.players[p] == player:
                continue
            #check for body collision
            if player.arena_object.collide(
                self.players[p].arena_object.x,
                self.players[p].arena_object.y,
                self.players[p].arena_object.width * self.players[p].arena_object.scale,
                self.players[p].arena_object.height * self.players[p].arena_object.scale,
            ):
                if player.attack == 1:
                    if self.players[p].attack == 0:
                        self.players[p].damage(1.0, player.name)
                    else:
                        self.players[p].damage(1.0, player.name)
                elif self.players[p]. attack == 1:
                    player.damage(1.0, 'himself')
                self.broadcast("collision between {} and {}".format(player.name, p))
                return True
        for wall in self.walls:
            if wall[6] == 0:
                height = 1 * wall[2]
                width = 20 * wall[0]
            else:
                height = 20 * wall[0]
                width = 1 * wall[2]
            if player.arena_object.collide(wall[3], wall[5], width, height):
                return True
        for bm in self.active_bonus_malus:
            if player.arena_object.collide(
                bm.arena_object.x,
                bm.arena_object.y,
                bm.arena_object.width * bm.arena_object.scale,
                bm.arena_object.height * bm.arena_object.scale,
            ):
                gevent.spawn(bm.activate_bonus, player)
        return False

    def engine_start(self):
        del self.greenlets['engine']
        print('engine started')
        while True:
            if (len(self.players) == 1 and self.started):
                self.finished = True
                self.winning_logic()
                self.restart_game(11)
                break
            elif (len(self.players) == 0):
                self.finished = True
                self.restart_game()
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
                    draw = self.attack_cmd_handler(player, player.attack_cmd)
                    # print player.attack_cmd
                    if draw:
                        player.update_gfx()
                    player.attack_cmd = None
            for animation in self.animations:
                animation.animate()
            t1 = uwsgi.micros() / 1000.0
            delta = t1 - t
            if delta < 33.33:
                gevent.sleep((33.33 - delta) / 1000.0)
        self.greenlets['engine'] = self.engine_start
        print("engine ended")

    def start(self):
        del self.greenlets['start']
        print("START!!")
        #self.warming_up = True

        while len(self.players) < self.min_players:
            for p in self.players.keys():
                self.players[p].update_gfx()
            gevent.sleep(1)
            if self.finished:
                self.greenlets['start'] = self.start
                print("ending")
                return

        warmup = self.warmup

        while warmup > 0:
            gevent.sleep(1.0)
            self.broadcast("warmup,{} seconds to start".format(warmup))
            warmup -= 1
        #self.warmup = False
        self.started = True
        #gevent.spawn(self.engine_start)
        gevent.sleep()
        self.broadcast("FIGHT!!!")
        gevent.sleep()

        bm_counter = 0
        while not self.finished:
            gevent.sleep(10.0)
            if len(self.bonus_malus_spawn_points) > 0:
                coordinates = self.bonus_malus_spawn_points.pop(randrange(len(self.bonus_malus_spawn_points)))
                choice(self.bonus_malus)(self, bm_counter, *(coordinates))
                bm_counter += 1
        gevent.sleep(1.0)
        self.broadcast("end")
        self.started = False
        self.greenlets['start'] = self.start
        print("end")
        gevent.sleep()

    def spawn_greenlets(self):
        for greenlet in self.greenlets:
            #if len(self.players) >= self.min_players:
            if len(self.players) >= 1:
                gevent.spawn(self.greenlets[greenlet])

    # place up to 8 waiting_players
    # in the player list and start the game again
    # unless less than 2 players are available
    def winning_logic(self):
        winner_name = self.players.keys()[0]
        self.players[winner_name].end('winner')

    def restart_game(self):
        countdown = 15
        while countdown > 0:
            self.broadcast('next game will start in {} seconds'.format(countdown))
            gevent.sleep(1)
            countdown -= 1
        self.finished = False
        self.players = {}
        if len(self.waiting_players) > 0:
            for player in self.waiting_players:
                self.players[player.name] = player
                if len(self.players) >= self.max_players:
                    break
        self.broadcast('waiting for players')


class Player(object):

    def __init__(self, game, name, avatar, fd, x, y, r, color, speed=15):
        self.game = game
        self.name = name
        self.avatar = avatar
        self.fd = fd

        self.arena_object = ArenaObject(x, y, r, speed)

        self.attack = 0
        self.energy = 100.0

        self.arena = "arena{}".format(uwsgi.worker_id())
        self.redis = redis.StrictRedis()
        self.channel = self.redis.pubsub()
        self.channel.subscribe(self.arena)
        self.redis_fd = self.channel.connection._sock.fileno()

        self.cmd = None
        self.attack_cmd = None
        self.bullet = Bullet(self.game, self)
        self.color = color

        # check if self.energy is 0, in such a case
        # trigger the kill procedure removing the player from the list
        # if after the death a single player remains, trigger the winning procedure
    def damage(self, amount, attacker):
        if not self.game.started:
            return
        self.energy -= amount
        if self.energy <= 0:
            self.game.broadcast(
                '{} was killed by {}'.format(self.name, attacker)
            )
            self.end('loser')
        else:
            self.update_gfx()

    def end(self, status):
        self.send_all('kill:{},{}'.format(status, self.name))
        del self.game.players[self.name]

    def send_all(self, msg):
        self.redis.publish(self.arena, msg)

    def update_gfx(self):
        msg = "{}:{},{},{},{},{},{},{},{},{}".format(
            self.name,
            self.arena_object.r,
            self.arena_object.x,
            30,
            self.arena_object.y,
            self.attack,
            self.energy,
            self.avatar,
            self.arena_object.scale,
            self.color
        )
        self.send_all(msg)

    def wait_for_game(self):
        while self.game.started or self.game.finished or self.name not in self.game.players:
            gevent.sleep(1)
            try:
                uwsgi.websocket_recv_nb()
            except IOError:
                import sys
                print sys.exc_info()
                if self.name in self.players:
                    self.end('leaver')
                return [""]


class Bullet(object):

    def __init__(self, game, player, damage=10, speed=50, _range=1500.0):
        self.game = game
        self.player = player
        self.arena_object = ArenaObject(self.player.arena_object.x, self.player.arena_object.y, 0.0, speed)
        self.is_shooting = 0
        self._range = _range
        self.damage = damage

    def shoot(self):
        if self.is_shooting > 0:
            return
        self.arena_object.x = self.player.arena_object.x
        self.arena_object.y = self.player.arena_object.y
        self.arena_object.r = self.player.arena_object.r
        self.is_shooting = self._range
        self.player.damage(1.0, 'himself')
        self.game.animations.append(self)

    def animate(self):
        self.arena_object.translate(self.arena_object.speed)
        if self.collision():
            self.is_shooting = 0
        else:
            self.is_shooting -= self.arena_object.speed
        msg = "!:{}:{},{},{},{},{}".format(
            self.player.name,
            self.arena_object.r,
            self.arena_object.x,
            50,
            self.arena_object.y,
            self.is_shooting
        )
        self.player.send_all(msg)
        if self.is_shooting <= 0:
            self.game.animations.remove(self)

    def collision(self):
        for p in self.game.players.keys():
            if self.game.players[p] == self.player:
                continue
            if self.arena_object.collide(
                self.game.players[p].arena_object.x,
                self.game.players[p].arena_object.y,
                self.game.players[p].arena_object.width * self.game.players[p].arena_object.scale,
                self.game.players[p].arena_object.height * self.game.players[p].arena_object.scale,
            ):

                self.game.players[p].damage(self.damage, self.player.name)
                return True

        for wall in self.game.walls:
            if wall[6] == 0:
                height = 1 * wall[2]
                width = 19.5 * wall[0]
            else:
                height = 19.5 * wall[0]
                width = 1 * wall[2]
            if self.arena_object.collide(wall[3], wall[5], width, height):
                return True
        return False


class Robotab(Arena):

    def __call__(self, e, sr):
        if e['PATH_INFO'] == '/':
            sr('200 OK', [('Content-Type', 'text/html')])
            return [open('robotab_ws.html').read()]

        if e['PATH_INFO'] == '/robotab.js':
            sr('200 OK', [('Content-Type', 'application/javascript')])
            return [open('static/js/robotab.js').read()]

        if e['PATH_INFO'] == '/robotab':
            uwsgi.websocket_handshake()
            username, avatar = uwsgi.websocket_recv().split(':')
            try:
                robot_coordinates = self.spawn_iterator.next()
            except StopIteration:
                self.spawn_iterator = iter(self.spawn_points)
                robot_coordinates = self.spawn_iterator.next()

            uwsgi.websocket_send('posters:{}'.format(';'.join(self.posters)))
            uwsgi.websocket_send('walls:{}'.format(str(self.walls).replace('),', ';').translate(None, "()")))
            player = Player(self, username, avatar, uwsgi.connection_fd(), *robot_coordinates)

            if self.started or self.finished or len(self.players) > self.max_players or len(self.waiting_players) > 0:
                print('{}:{}:{}:{}'.format(self.started, self.finished, len(self.players) > self.max_players, len(self.waiting_players) > 0))
                self.waiting_players.append(player)
                uwsgi.websocket_send("arena:hey {}, wait for next game".format(player.name))
                player.wait_for_game()
                self.waiting_players.remove(player)
            else:
                self.players[player.name] = player

            self.spawn_greenlets()

            for p in self.players.keys():
                self.players[p].update_gfx()

            while True:
                ready = gevent.select.select([player.fd, player.redis_fd], [], [], timeout=4.0)

                if not ready[0]:
                    uwsgi.websocket_recv_nb()

                for fd in ready[0]:
                    if fd == player.fd:
                        try:
                            msg = uwsgi.websocket_recv_nb()
                        except IOError:
                            import sys
                            print sys.exc_info()
                            if player.name in self.players:
                                player.end('leaver')
                            return [""]
                        if msg and not self.finished:
                            self.msg_handler(player, msg)
                    elif fd == player.redis_fd:
                        msg = player.channel.parse_response()
                        if msg[0] == 'message':
                            uwsgi.websocket_send(msg[2])


application = Robotab()
