from bulletphysics import *
import math

broadphase = DbvtBroadphase()
collisionConfiguration = DefaultCollisionConfiguration()
dispatcher = CollisionDispatcher(collisionConfiguration)
solver = SequentialImpulseConstraintSolver()
world = DiscreteDynamicsWorld(dispatcher, broadphase, solver, collisionConfiguration)
world.setGravity(Vector3(0, -9.81, 0))


ground_shape = StaticPlaneShape(Vector3(0, 1, 0), 1)
q_ground = Quaternion(0, 0, 0, 1)
ground_motion_state = DefaultMotionState(
    Transform(q_ground, Vector3(0, -1, 0)))
construction_info = RigidBodyConstructionInfo(
    0, ground_motion_state, ground_shape, Vector3(0, 0, 0))
# construction_info.m_friction = 1.0
ground = RigidBody(construction_info)
world.addRigidBody(ground)

sphere_shape = SphereShape(1)
q_sphere = Quaternion(0, 0, 0, 1)
sphere_motion_state = DefaultMotionState(
    Transform(q_sphere, Vector3(0, 50, 0)))
fallInertia = Vector3(0, 0, 0)
sphere_shape.calculateLocalInertia(1, fallInertia)
sphere_contruction_info = RigidBodyConstructionInfo(
    1, sphere_motion_state, sphere_shape, fallInertia)
sphere = RigidBody(sphere_contruction_info)
world.addRigidBody(sphere)


while True:
    world.stepSimulation(1/60.0, 10)
    trans = Transform()
    sphere_motion_state.getWorldTransform(trans)
    origin = trans.getOrigin()
    pos_x = origin.getX()
    pos_y = origin.getY()
    pos_z = origin.getZ()
    print(math.ceil(pos_x), math.ceil(pos_y), math.ceil(pos_z))
