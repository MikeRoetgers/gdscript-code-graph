extends Character
class_name Player

const BulletScene = preload("res://weapons/bullet.gd")

var speed: float = 200.0
var score: int = 0
var active_bullet: Bullet

func _process(delta: float) -> void:
    if Input.is_action_pressed("move_right"):
        velocity.x = speed
    elif Input.is_action_pressed("move_left"):
        velocity.x = -speed
    else:
        velocity.x = 0

func shoot() -> Bullet:
    var b = BulletScene.new()
    add_child(b)
    return b
