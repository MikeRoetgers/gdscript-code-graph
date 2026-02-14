extends "res://actors/character.gd"

var patrol_points: Array = []

func _process(delta: float) -> void:
    for point in patrol_points:
        if position.distance_to(point) < 10.0:
            _advance_patrol()
