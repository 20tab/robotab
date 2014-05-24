import math


class Vector3(object):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z

    # apply a quaternion to a vector
    def applyQuaternion(self, q):
        x = self.x
        y = self.y
        z = self.z

        qx = q.x
        qy = q.y
        qz = q.z
        qw = q.w

        ix =  qw * x + qy * z - qz * y
        iy =  qw * y + qz * x - qx * z
        iz =  qw * z + qx * y - qy * x
        iw = -qx * x - qy * y - qz * z

        self.x = ix * qw + iw * -qx + iy * -qz - iz * -qy
        self.y = iy * qw + iw * -qy + iz * -qx - ix * -qz
        self.z = iz * qw + iw * -qz + ix * -qy - iy * -qx

        return self

    # sum of vectors
    def add(self, v):
        self.x += v.x
        self.y += v.y
        self.z += v.z

    def multiplyScalar(self, n):
        self.x *= n
        self.y *= n
        self.z *= n
        return self


class Quaternion(object):

    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        self._x = z
        self._y = y
        self._z = z
        self._w = w

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, n):
        self._x = n
        self.updateEuler()

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, n):
        self._y = n
        self.updateEuler()

    @property
    def z(self):
        return self._z

    @z.setter
    def z(self, n):
        self._z = n
        self.updateEuler()

    @property
    def w(self):
        return self._w

    @w.setter
    def w(self, n):
        self._w = n
        self.updateEuler()

    def updateEuler(self):
        self.euler.setFromQuaternion(self)

    def setFromEuler(self, euler):
        c1 = math.cos(euler._x / 2)
        c2 = math.cos(euler._y / 2)
        c3 = math.cos(euler._z / 2)
        s1 = math.sin(euler._x / 2)
        s2 = math.sin(euler._y / 2)
        s3 = math.sin(euler._z / 2)
        self._x = s1 * c2 * c3 + c1 * s2 * s3
        self._y = c1 * s2 * c3 - s1 * c2 * s3
        self._z = c1 * c2 * s3 + s1 * s2 * c3
        self._w = c1 * c2 * c3 - s1 * s2 * s3


class Euler(object):

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self._x = z
        self._y = y
        self._z = z

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, n):
        self._x = n
        self.updateQuaternion()

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, n):
        self._y = n
        self.updateQuaternion()

    @property
    def z(self):
        return self._z

    @z.setter
    def z(self, n):
        self._z = n
        self.updateQuaternion()

    def updateQuaternion(self):
        self.quaternion.setFromEuler(self)

    def clamp(self, x):
        return min(max(x, -1), 1)

    def setFromQuaternion(self, q):
        sqx = q.x * q.x
        sqy = q.y * q.y
        sqz = q.z * q.z
        sqw = q.w * q.w

        self._x = math.atan2(2 * (q.x * q.w - q.y * q.z), (sqw - sqx - sqy + sqz))
        self._y = math.asin(self.clamp(2 * (q.x * q.z + q.y * q.w)))
        self._z = math.atan2(2 * (q.z * q.w - q.x * q.y), (sqw + sqx - sqy - sqz))


class MathPlayer(object):

    def __init__(self, x=0, y=0, z=0):
        self.scale = 7
        self.radius = 8
        self.position = Vector3(x, y, z)
        self.rotation = Euler()
        self.quaternion = Quaternion()
        self.quaternion.euler = self.rotation
        self.rotation.quaternion = self.quaternion

    def position_tuple(self):
        return (self.position.x, self.position.y, self.position.z)

    def set_position(self, pos):
        self.position.x = pos[0]
        self.position.y = pos[1]
        self.position.z = pos[2]

    def translateZ(self, n):
        v1 = Vector3(0, 0, 1)
        v1.applyQuaternion(self.quaternion)
        self.position.add(v1.multiplyScalar(n))

    def translateX(self, n):
        v1 = Vector3(1, 0, 0)
        v1.applyQuaternion(self.quaternion)
        self.position.add(v1.multiplyScalar(n))

    def rotateY(self, n):
        self.rotation.y += n
        self.rotation.updateQuaternion()

    def circleCollide(self, x, z, r):
        if self.position.x > x:
            x1 = (self.position.x - x) ** 2
        else:
            x1 = (x - self.position.x) ** 2

        if self.position.z > z:
            x2 = (self.position.z - z) ** 2
        else:
            x2 = (z - self.position.z) ** 2

        r1 = ((self.radius * self.scale) + r) ** 2

        if (x1+x2) <= r1:
            return True
        return False
