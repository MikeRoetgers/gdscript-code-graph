extends Area2D
class_name Bullet

var speed: float = 600.0

func _physics_process(delta: float) -> void:
    position += transform.x * speed * delta
