from flask import jsonify, request
from sqlalchemy import func
from functools import wraps


from datetime import datetime, timedelta, timezone


from .models import Like, User, InvalidToken, Follow
from . import jwt


def get_blog_likes(blog):
    try:
        total_likes = Like.query.with_entities(Like.blog_id, func.sum(Like.like)).filter_by(blog_id=blog.id).all()

        likes = [like[1] for like in total_likes]
        
        return likes
    
    except Exception as e:
        return jsonify({"error": str(e)})
    


def get_comment_likes(comment):
    try:
        total_likes = Like.query.with_entities(Like.comment_id, func.sum(Like.like)).filter_by(comment_id=comment.id).all()

        likes = [like[1] for like in total_likes]
        
        return likes
    
    except Exception as e:
        return jsonify({"error": str(e)})
    


def get_reply_likes(reply):
    try:
        total_likes = Like.query.with_entities(Like.reply_id, func.sum(Like.like)).filter_by(reply_id=reply.id).all()

        likes = [like[1] for like in total_likes]
        
        return likes
    
    except Exception as e:
        return jsonify({"error": str(e)})


def serialize_replies(reply):
    return {
        "Reply": reply.replies,
        "Reply user's name": reply.users.username,
        "Reply Likes": get_reply_likes(reply),
        "Replied": [serialize_replies(rep) for rep in reply.children]
    }


def cache(f):
    cached = {}
    count = {}

    @wraps(f)
    def inner(*args, **kwargs):

        query = ""
        param = request.args.items(multi=True)

        for _, value in param:
            query += value

        if query:
            if query in cached:
                print(f"Returning {query} from memory")
                return cached[query]
            
            if query not in count:
                count[query] = {"count": 0}

            count[query]["count"] += 1

            if count[query]["count"] >=3:
                print(f"Cachning {query} to memory")
                result = f(*args, **kwargs)

                cached[query] = result

                return result
            
        return f(*args, **kwargs)
    return inner


def rate_limt(MAX_REQUEST=0, BANNED_TIME=0):
    def decorator(f):
        ip_book = {}
        @wraps(f)
        def inner(*args, **kwargs):

            ip = request.remote_addr
            now = datetime.now(timezone.utc)

            if ip not in ip_book:
                ip_book[ip] = {
                    "count": 0,
                    "first request": now,
                    "banned until": None
                }

            ip_book[ip]["count"] += 1

            if ip_book[ip]["banned until"] is not None and now < ip_book[ip]["banned until"]:
                return jsonify({"Message": f"You are been temporarily banned. Try again after {BANNED_TIME} minutue(s)."}), 403
            

            if now - ip_book[ip]["first request"] > timedelta(minutes=BANNED_TIME):
                ip_book[ip] = {
                    "count": 1,
                    "first request": now,
                    "banned until": None
                }

            if ip_book[ip]["count"] > MAX_REQUEST:
                ip_book[ip]['banned until'] = now + timedelta(minutes=BANNED_TIME)
                return jsonify({"Message": "You have exceeded the daily request limit on this route."}), 403
            

            return f(*args, **kwargs)
        
        return inner
    
    return decorator



def user_id_int(id):
    if isinstance(id,int) == False:
        user_id = int(id)

        return user_id
    
    return id

def get_user(id):
    user = User.query.get(id)

    if user:
        return user
    
    return False


@jwt.token_in_blocklist_loader
def is_token_in_blocklist(data, decrypt):
    jti = decrypt['jti']

    return InvalidToken.is_jti_valid(jti)

def validate_name(x):
    """
    This function is meant to screen invalid inputs from data sent by the clients.
    """
    numbers = "1,2,3,4,5,6,7,8,9,0"
    symbols = "!@#$%^&*()}{[]?/>.<,`~|"";:=+_"

    if x.isdigit():
        return {"valid": False, "data": jsonify({"error": "Name cannot be numbers. Please input a valid name."}), "code": 200}
    elif len(x) <=2:
        return {"valid": False, "data": jsonify({"error": "Name too short or name cannot be empty."}), "code": 200}
    elif any(num in numbers for num in x):
        return {"valid": False, "data": jsonify({"error": "Numbers should not be in name. Please input a valid name."}), "code": 200}
    elif any(sym in symbols for sym in x):
        return {"valid": False, "data": jsonify({"error": "Name has no special characters. Please input a valid name."}), "code": 200}
    else:
        return {"valid": True, "data": x, "code": 200}


def is_following(follower: int, following: int) -> int:
    '''This finction checks if a user is already following another user. 
       if so it ensures there is no duplicate and it also ensures users cannot follow themseleves
    '''
    if follower == following:
        return jsonify({"error": "You cannot follow yourself"}), 200
    
    if Follow.query.filter_by(follower_user_id=follower, followed_user_id=following).first():
        return jsonify({"error": "You are already following this user."}), 200