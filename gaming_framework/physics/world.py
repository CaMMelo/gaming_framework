import heapq
from dataclasses import dataclass, field

import numpy as np

from gaming_framework.geometry.shape import Point2D, Rectangle
from gaming_framework.physics.body import Body
from gaming_framework.physics.body_pair import BodyPair
from gaming_framework.physics.collision_shape import CollisionShape
from gaming_framework.spatial_structures.spatial_structure import SpatialStructure


@dataclass
class World:
    visible_area: Rectangle
    spatial_struct: SpatialStructure

    _moving_bodies: dict = field(init=False, default_factory=dict)
    _sweept_bodies: dict = field(init=False, default_factory=dict)
    _movement_spatial_struct: SpatialStructure = field(init=False, default=None)
    _collision_candidates: list = field(init=False, default_factory=list)

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other) -> bool:
        return id(self) == id(other)

    def __calculate_sweept_body(self, body: Body, new_pos: Point2D) -> Body:
        top = body.bounding_box.center.y + body.bounding_box.radius
        left = body.bounding_box.center.x - body.bounding_box.radius
        bottom = new_pos.center.y - body.bounding_box.radius
        right = new_pos.center.x + body.bounding_box.radius
        top_left = Point2D(left, top)
        bottom_right = Point2D(right, bottom)
        sweept_shape = Rectangle(top_left, bottom_right)
        collision_shape = CollisionShape(sweept_shape)
        sweept_body = Body(collision_shape)
        return sweept_body

    def __time_of_collision(self, body_a: Body, body_b: Body) -> float:
        distance = (
            body_a.bounding_box.radius**2
            + 2 * body_a.bounding_box.radius * body_b.bounding_box.radius
            + body_b.bounding_box.radius**2
        )
        a = (body_a.speed.x - body_b.speed.x) * (body_a.speed.x - body_b.speed.x) + (
            body_a.speed.y - body_b.speed.y
        ) * (body_a.speed.y - body_b.speed.y)
        b = 2 * (
            (body_a.bounding_box.center.x - body_b.bounding_box.center.x)
            * (body_a.speed.x - body_b.speed.x)
            + (body_a.bounding_box.center.y - body_b.bounding_box.center.y)
            * (body_a.speed.y - body_b.speed.y)
        )
        c = (
            (body_a.bounding_box.center.x - body_b.bounding_box.center.x)
            * (body_a.bounding_box.center.x - body_b.bounding_box.center.x)
            + (body_a.bounding_box.center.y - body_b.bounding_box.center.y)
            * (body_a.bounding_box.center.y - body_b.bounding_box.center.y)
            - distance
        )
        delta = b**2 - 4 * a * c
        if delta < 0:
            return -1
        d = np.sqrt(delta)
        t1 = (-b - d) / (2 * a)
        t2 = (-b + d) / (2 * a)
        if t1 < 0 and t2 > 0 and b <= 0:
            return 0
        return t1

    def __push_to_collision_candidates(
        self, pair: BodyPair, delta_time: float, start_time: float
    ):
        toc = self.__time_of_collision(pair.body_a, pair.body_b)
        if 0 <= toc <= (start_time + delta_time):
            heapq.heappush(self._collision_candidates, (toc, pair))

    def __remove_moving_body(self, body: Body):
        if body not in self._moving_bodies:
            return
        (_, _, sweept_body) = self._moving_bodies[body]
        del self._moving_bodies[body]
        del self._sweept_bodies[sweept_body]
        self._movement_spatial_struct.remove(sweept_body)

    def __predict_movement(self, body: Body, delta_time: float):
        if body.is_static:
            return
        new_pos = body.predict_position(delta_time)
        if new_pos == body.position:
            return
        sweept_body = self.__calculate_sweept_body(body, new_pos)
        self._moving_bodies[body] = (body.position, new_pos, sweept_body)
        self._sweept_bodies[sweept_body] = body
        self._movement_spatial_struct.insert(sweept_body)

    def __query_collisions_with_moving_bodies(
        self, body: Body, delta_time: float, start_time: float
    ):
        (_, _, sweept_body) = self._moving_bodies[body]
        pairs = []
        for candidate in (
            BodyPair(body, self._sweept_bodies[sweept_body_b])
            for sweept_body_b in self._movement_spatial_struct.query(sweept_body.shape)
            if (sweept_body != sweept_body_b)
            and (body != self._sweept_bodies[sweept_body_b])
        ):
            if candidate not in pairs:
                pairs.append(candidate)
                self.__push_to_collision_candidates(candidate, delta_time, start_time)

    def __query_collisions_with_static_bodies(
        self, body: Body, delta_time: float, start_time: float
    ):
        (_, _, sweept_body) = self._moving_bodies[body]
        pairs = []
        for candidate in (
            BodyPair(body, static_body)
            for static_body in self.spatial_struct.query(sweept_body.shape)
            if (static_body not in self._moving_bodies)
        ):
            if candidate not in pairs:
                pairs.append(candidate)
                self.__push_to_collision_candidates(candidate, delta_time, start_time)

    def __update_collision_candidates(
        self, body: Body, delta_time: float, start_time: float
    ):
        if body not in self._moving_bodies:
            return
        self.__query_collisions_with_moving_bodies(body, delta_time, start_time)
        self.__query_collisions_with_static_bodies(body, delta_time, start_time)

    def __handle_contact(
        self, body_a: Body, body_b: Body, current_time: float, end_time: float
    ):
        self.__remove_moving_body(body_a)
        self.__remove_moving_body(body_b)
        remaining_time = end_time - current_time
        self.__predict_movement(body_a, remaining_time)
        self.__predict_movement(body_b, remaining_time)

    def __update_body_forces(self, body_a: Body, body_b: Body):
        v1 = (
            body_a.speed.scalar_mult(body_a.mass)
            + body_b.speed.scalar_mult(body_b.mass)
            + (body_b.speed - body_a.speed).scalar_mult(body_b.mass)
        ).scalar_div(body_a.mass + body_b.mass)
        v2 = (
            body_a.speed.scalar_mult(body_a.mass)
            + body_b.speed.scalar_mult(body_b.mass)
            + (body_a.speed - body_b.speed).scalar_mult(body_b.mass)
        ).scalar_div(body_a.mass + body_b.mass)

        if not body_a.is_static:
            body_a.speed = v1
        if not body_b.is_static:
            body_b.speed = v2

    def __resolve_collision(
        self,
        body_a: Body,
        body_b: Body,
        time_of_collision: float,
        current_time: float,
        end_time: float,
    ):
        handle_contact = body_a.is_tangible and body_b.is_tangible
        if handle_contact:
            time_diff = 0
            if time_of_collision == 0:
                time_diff = 1e-2
            body_a.update(current_time - time_diff)
            body_b.update(current_time - time_diff)
            self.__update_body_forces(body_a, body_b)
            self.__handle_contact(body_a, body_b, current_time, end_time)
        body_a.handle_collision(body_b)
        body_b.handle_collision(body_a)

    def __check_collision(
        self,
        body_a: Body,
        body_b: Body,
        time_of_collision: float,
        current_time: float,
        end_time: float,
    ):
        comparing_shape_a = body_a.shape
        comparing_shape_b = body_b.shape
        if body_a in self._moving_bodies and time_of_collision > 0:
            position = body_a.predict_position(time_of_collision)
            comparing_shape_a = body_a.shape.center_to(position)
        if body_b in self._moving_bodies and time_of_collision > 0:
            position = body_b.predict_position(time_of_collision)
            comparing_shape_b = body_b.shape.center_to(position)

        if comparing_shape_a.collides_with(comparing_shape_b):
            self.__resolve_collision(
                body_a,
                body_b,
                time_of_collision,
                current_time,
                end_time,
            )

    def __detect_collisions(self, delta_time: float):
        current_time = 0
        while self._collision_candidates:
            time_of_collision, pair = heapq.heappop(self._collision_candidates)
            self.__check_collision(
                pair.body_a, pair.body_b, time_of_collision, current_time, delta_time
            )
            current_time += time_of_collision

    def get_visible_bodies(self) -> list[Body]:
        return self.spatial_struct.query(self.visible_area)

    def update(self, delta_time: float):
        self._moving_bodies = {}
        self._sweept_bodies = {}
        self._movement_spatial_struct = self.spatial_struct.empty_copy()
        self._collision_candidates = []
        for body in self.spatial_struct.get_objects():
            self.__predict_movement(body, delta_time)
        for body in self._moving_bodies:
            self.__update_collision_candidates(body, delta_time, start_time=0)
        self.__detect_collisions(delta_time)
        for body in self._moving_bodies:
            body.update(delta_time)
