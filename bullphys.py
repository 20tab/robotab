from bulletphysics import *
import math
import redis
import uwsgi
import gevent
import gevent.select

class Ramp(object):
    def __init__(self, name, world, x, y, z, w, h, d):
        self.shape = BoxShape(Vector3(w, h, d));
        q = Quaternion(0,0,0,1)
        q.setRotation(Vector3(0.0, 0.0, 1.0), 0.3)
        self.motion_state = DefaultMotionState( Transform(q, Vector3(x, y, z)) )
        print self.motion_state
        construction_info = RigidBodyConstructionInfo(0, self.motion_state, self.shape, Vector3(0,0,0))
        self.body = RigidBody( construction_info )
        world.ramps[name] = self
        world.world.addRigidBody(self.body)
        self.trans = Transform()
        self.origin = self.trans.getOrigin()
        self.name = name
        self.last_msg = None
        self.world = world
        self.w = w
        self.h = h
        self.d = d

    def draw(self):
        self.motion_state.getWorldTransform(self.trans)
        pos_x = self.origin.getX()
        pos_y = self.origin.getY()
        pos_z = self.origin.getZ()
        quaternion = self.trans.getRotation()
        rot_x = quaternion.getX()
        rot_y = quaternion.getY()
        rot_z = quaternion.getZ()
        rot_w = quaternion.getW()
        msg = '{name}:{pos_x},{pos_y},{pos_z:},{size_x},{size_y},{size_z},{rot_x:.2f},{rot_y:.2f},{rot_z:.2f},{rot_w:.2f}'.format(
            name=self.name,
            pos_x=int(pos_x),
            pos_y=int(pos_y),
            pos_z=int(pos_z),
            size_x=self.w,
            size_y=self.h,
            size_z=self.d,
            rot_x=rot_x,
            rot_y=rot_y,
            rot_z=rot_z,
            rot_w=rot_w,
        )
        if msg != self.last_msg:
            print msg
            self.world.redis.publish('phys', msg)
            self.last_msg = msg


class Box(object):
    def __init__(self, name, world, weight, size, x, y, z, r=0.0):
        self.mass = weight
        self.shape = BoxShape(Vector3(size, size, size));
        self.motion_state = DefaultMotionState( Transform(Quaternion(0,0,0,1), Vector3(x, y, z)) )
        print self.motion_state
        self.inertia = Vector3(0,0,0)
        self.shape.calculateLocalInertia(self.mass, self.inertia)
        construction_info = RigidBodyConstructionInfo(self.mass, self.motion_state, self.shape, self.inertia)
        construction_info.m_friction = 0.8
        self.body = RigidBody( construction_info )
        world.boxes[name] = self
        world.world.addRigidBody(self.body)
        self.trans = Transform()
        self.origin = self.trans.getOrigin()
        self.name = name
        self.rx = 0
        self.ry = 0
        self.rz = 0
        self.size = size
        self.last_msg = None
        self.world = world
        self.matrix = [0.0] * 16

    def draw_bad(self):
        self.motion_state.getWorldTransform(self.trans)
        self.trans.getOpenGLMatrix(self.matrix)
        msg = '{name}:{matrix}'.format(name=self.name,matrix=','.join(map(str,self.matrix)))
        if msg != self.last_msg:
            print msg
            if msg.startswith('box0'):
                print msg
            self.world.redis.publish('phys', msg)
            self.last_msg = msg

    def draw(self):
        self.motion_state.getWorldTransform(self.trans)
        pos_x = self.origin.getX()
        pos_y = self.origin.getY()
        pos_z = self.origin.getZ()
        quaternion = self.trans.getRotation()
        rot_x = quaternion.getX()
        rot_y = quaternion.getY()
        rot_z = quaternion.getZ()
        rot_w = quaternion.getW()
        msg = '{name}:{pos_x},{pos_y},{pos_z:},{size_x},{size_y},{size_z},{rot_x:.2f},{rot_y:.2f},{rot_z:.2f},{rot_w:.2f}'.format(
            name=self.name,
            pos_x=int(pos_x),
            pos_y=int(pos_y),
            pos_z=int(pos_z),
            size_x=self.size,
            size_y=self.size,
            size_z=self.size,
            rot_x=rot_x,
            rot_y=rot_y,
            rot_z=rot_z,
            rot_w=rot_w,
        )
        if msg != self.last_msg:
            print msg
            if msg.startswith('box0'):
                print msg
            self.world.redis.publish('phys', msg)
            self.last_msg = msg


class World(object):
    def __init__(self):
        self.collisionConfiguration = DefaultCollisionConfiguration()
        self.dispatcher = CollisionDispatcher(self.collisionConfiguration)
        self.solver = SequentialImpulseConstraintSolver()
        self.broadphase = DbvtBroadphase()
        self.world = DiscreteDynamicsWorld(self.dispatcher, self.broadphase, self.solver, self.collisionConfiguration)
        self.world.setGravity( Vector3(0,-9.81,0) )
        print self.world
        q = Quaternion(0,0,0,1)
        #q.setRotation(Vector3(0, 0, 1), 30)
        self.ground_motion_state = DefaultMotionState( Transform(q, Vector3(0,1,0)) )
        print self.ground_motion_state
        self.ground_shape = StaticPlaneShape(Vector3(0,1,0),1)
        construction_info = RigidBodyConstructionInfo(0, self.ground_motion_state, self.ground_shape, Vector3(0,0,0))
        construction_info.m_friction = 0.8
        self.ground = RigidBody( construction_info )
        print self.ground
        self.world.addRigidBody(self.ground)
        self.boxes = {}
        self.ramps = {}
        self.redis = redis.StrictRedis()
        self.redis_pubsub = redis.StrictRedis()
        self.channel = self.redis_pubsub.pubsub()
        self.channel.subscribe('phys')
        self.redis_fd = self.channel.connection._sock.fileno()

def physic_engine(world):
    while True:
        t = uwsgi.micros() / 1000.0
        world.world.stepSimulation(1, 30)
        for name,box in world.boxes.items():
            box.draw()
        for name,ramp in world.ramps.items():
            ramp.draw()
        t1 = uwsgi.micros() / 1000.0
        delta = t1 - t
        if delta < 33.33:
            gevent.sleep((33.33 - delta) / 1000.0)


def application(e, sr):
    if e['PATH_INFO'] == '/phys':
        uwsgi.websocket_handshake()

        w = World()
        me = Box('box0', w, 1000, 250, -1000, 250, 0)
        box1 = Box('box1', w, 20, 50, -1000, 250, 0)
        box2 = Box('box2', w, 20, 50, -1500, 350, 0)
        box3 = Box('box3', w, 20, 50, -1500, 450, 0)
        box4 = Box('box4', w, 200, 150, -1500, 550, 0)

        ramp = Ramp('ramp0', w, 400, 0, 100, 7000, 10, 400)

        print "BOX DRAWING COMPLETE"

        gevent.spawn(physic_engine, w)
        ufd = uwsgi.connection_fd()
        while True:

            ready = gevent.select.select([ufd, w.redis_fd], [], [], timeout=4.0)

            if not ready[0]:
                uwsgi.websocket_recv_nb()

            for fd in ready[0]:
                if fd == ufd:
                    try:
                        msg = uwsgi.websocket_recv_nb()
                        if msg == 'fw':
                            orientation = me.body.getOrientation()
                            v = Vector3(0, 0, 5000).rotate(orientation.getAxis(), orientation.getAngle())
                            me.body.activate(True)
                            me.body.applyCentralImpulse( v )
                        elif msg == 'bw':
                            orientation = me.body.getOrientation()
                            v = Vector3(0, 0, -5000).rotate(orientation.getAxis(), orientation.getAngle())
                            me.body.activate(True)
                            me.body.applyCentralImpulse( v )
                        elif msg == 'rl':
			    orientation = me.body.getOrientation()
                            v = Vector3(0, 2000000, 0).rotate(orientation.getAxis(), orientation.getAngle())
                            me.body.activate(True)
                            me.body.applyTorqueImpulse( v )
                        elif msg == 'rr':
			    orientation = me.body.getOrientation()
                            v = Vector3(0, -2000000, 0).rotate(orientation.getAxis(), orientation.getAngle())
                            me.body.activate(True)
                            me.body.applyTorqueImpulse( v )
                            #me.body.applyForce( Vector3(0, 0, 10000), Vector3(-200, 0, 0))
                            #me.body.applyForce( Vector3(0, 0, -10000), Vector3(200, 0, 0))
                    except IOError:
                        import sys
                        print sys.exc_info()
                        return [""]
                elif fd == w.redis_fd:
                    msg = w.channel.parse_response()
                    if msg[0] == 'message':
                        uwsgi.websocket_send(msg[2])

