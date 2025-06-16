from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, get_jwt, jwt_required


from .models import db, Blog, Tag, User, Comment, Reply, Like, InvalidToken
from .helper import get_blog_likes, serialize_replies, get_comment_likes, get_reply_likes, cache, get_user, rate_limt

bp = Blueprint("bp", __name__)

@bp.route("/")
def home():
    return jsonify({
        "Message": "Welcome! Below is a guide on how to use my API.",
        "How to use API": "API not hard to use. The endpoints will guide you on how to access contents from the API.",
        "Endpoints": [{
            "Base URL": "localhost:5000",
            "To view all blogs": "/blogs",
            "To search for a blog": [{
                "Base on title": "/search?q=(The title here)",
                "Base on tag": "/search?t=(You tag here)",
                "Base on category": "/search?c=(You category here)",
                "Base on Author": "/search?a=(Name of author)",
                "Base on date published": "/search?p=(Date here)",
                "For a specific search": "/search?q=(title here)&c=(category here)&a=(name of author)"
            }]
        }],
        "Notice": "I will release more endpoints for developers to be able to have more functionalities with the API",
        "Version": "v1"
    }), 200


@bp.route("/blogs", methods=["POST"])
@jwt_required()
def post_blog():
    if request.method == "POST":
        data = request.get_json()

        if data:
            try:
                user_id = get_jwt_identity()
                if user_id is not None:
                    username = get_user(user_id)
                    if username:
                        new_blog = Blog(title=data["title"], content=data['content'], category=data['category'], author=username.username, user_id=user_id)
                        for i in range(len(data['tag'])):
                            new_tag = Tag(name=data['tag'][i])
                            db.session.add(new_tag)
                            new_blog.tags.append(new_tag)
                    
                        db.session.add(new_blog)

                    else:
                        return jsonify({"error": "No user found!."})

                else:
                    new_blog = Blog(title=data["title"], content=data['content'], category=data['category'])
                    for i in range(len(data['tag'])):
                        new_tag = Tag(name=data['tag'][i])
                        db.session.add(new_tag)
                        new_blog.tags.append(new_tag)
                    
                    db.session.add(new_blog)

            except Exception as e:
                db.session.rollback()
                return jsonify({"Error": str(e)}), 500
            else:
                db.session.commit()
                return jsonify({"Message": "Blog added successfully."}), 201


@bp.route("/blogs")
@jwt_required()
def view_blogs():
    blogs = Blog.query.all()


    return jsonify({
        "Blogs": [{
            "id": blog.id,
            "Title": blog.title,
            "Content": blog.content,
            "Category": blog.category,
            "Blog Likes": get_blog_likes(blog),
            "Author": blog.author,
            "Interactions": [{
                "id": comment.id,
                "Comment": comment.content,
                "Comment user's name": comment.users.username,
                "Comment Likes": get_comment_likes(comment),
                "ReplyContent": [{
                    "id": reply.id,
                    "Reply": reply.replies,
                    "Reply user's name": reply.users.username,
                    "Reply Likes": get_reply_likes(reply)
                } for reply in comment.replies]
            } for comment in blog.comments],
            "Date Pub": blog.published_date.strftime("%Y-%m-%d"),
            "Tags": [tag.name for tag in blog.tags]
        } for blog in blogs]
    }), 200



@bp.route("/delete-blog/<int:blog_id>", methods=["DELETE"])
@jwt_required()
def delete_blog(blog_id: int) -> int:
    if request.method == "DELETE":
        user = get_jwt_identity()
        blog = Blog.query.filter_by(id=blog_id).first()

        try:
            if int(user) == blog.user_id:
                db.session.delete(blog)
            else:
                return jsonify({"error": "Can't delete blog you didn't post."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
        else:
            db.session.commit()
            return jsonify({"message": "Blog deleted"}), 200
        

@bp.route("/delete-tag/<int:tag_id>", methods=["DELETE"])
@jwt_required()
def delete_tag(tag_id: int) -> int:
    if request.method == "DELETE":
        tag = Tag.query.filter_by(id=tag_id).first()
        user = get_jwt_identity()

        user_id = [{
            "id": blog.user_id
        } for blog in tag.blogs]

        try:
            if int(user) == user_id[0]["id"]:
                db.session.delete(tag)
            else:
                return jsonify({"error": "Can't delete a tag not made by you."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
        else:
            db.session.commit()
            return jsonify({"message": "Tag deleted"}), 200
        

@bp.route("/register", methods=["POST"])
def add_user():
    if request.method == "POST":
        data = request.get_json()
        user = User.query.filter_by(email=data["email"]).first()

        if data:
            try:
                if user:
                    return jsonify({"error": "User already exists."})
                
                new_user = User(username=data["username"], email=data["email"], password=data['password'])

                db.session.add(new_user)
            except Exception as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 500
            else:
                db.session.commit()
                return jsonify({"Message": "User added successfully."}), 201


@bp.route("/login", methods=["POST"])
def login():
    if request.method == "POST":
        data = request.get_json()

        user = User.query.filter_by(username=data["username"]).first()

        try:
            if user:
                if data["password"] == user.password:
                    token = create_access_token(identity=str(user.id))

                    return jsonify({"token": token}), 200
                
                return jsonify({"error": "Incorrect password"}), 200
            
            return jsonify({"error": "In correct username"}), 200
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        

@bp.route("/view-users")
@rate_limt(MAX_REQUEST=3)
def view_users():
    users = User.query.all()

    return jsonify({"Users": [{
        "username": user.username,
        "email": user.email
    } for user in users]}), 200



@bp.route("/add-comment/<int:blog_id>", methods=["POST"])
@jwt_required()
def add_comment(blog_id: int) -> int:
    if request.method == "POST":
        data = request.get_json()
        user_id = get_jwt_identity()
        print(f"User: {user_id}| Blog: {blog_id}")

        if data:
            try:
                user = User.query.filter_by(id=user_id).first()
                blog = Blog.query.filter_by(id=blog_id).first()

                if user:
                    if blog:
                        new_comment = Comment(content=data['content'], user_id=user.id, blog_id=blog.id)
                        db.session.add(new_comment)

                        db.session.commit()
                        return jsonify({"Message": "Comment added Successfully."}), 201
                    
                    return jsonify({"error": "No blog found"}), 200
                
                return jsonify({"error": "No user found"}), 200
            except Exception as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 500


@bp.route("/view-comment")
@rate_limt(MAX_REQUEST=3)
def view_comment():
    comments = Comment.query.all()

    return jsonify({"Comments": [{
        "Content": comment.content,
        "Blog": {
            "Title": comment.blogs.title,
            "Content": comment.blogs.content
        },
        "User": comment.users.username
    } for comment in comments]}), 200


@bp.route("/delete-comment/<int:comment_id>", methods=["DELETE"])
@jwt_required()
def delete_comment(comment_id: int) -> int:
    if request.method == "DELETE":
        user = get_jwt_identity()

        try:
            comment = Comment.query.filter_by(id=comment_id).first_or_404()
            
            if comment:
                if int(user) == comment.user_id:
                    db.session.delete(comment)

                    db.session.commit()

                    return jsonify({"Message": "Comment successfully deleted."}), 200
                
                return jsonify({"error": "You can't delete comment u didn't make."}), 200
            
            return jsonify("No comment found."), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
        


@bp.route("/reply-comment/<int:id>/<int:blog_id>", methods=["POST"])
@jwt_required()
def add_reply(id: int, blog_id: int) -> int:
    if request.method == "POST":
        data = request.get_json()
        user_id = get_jwt_identity()

        try:
            user = User.query.filter_by(id=user_id).first_or_404()
            comment = Comment.query.filter_by(id=id).first_or_404()
            blog = Blog.query.filter_by(id=blog_id).first_or_404()

            if user:
                if blog:
                    if comment:
                        new_reply = Reply(replies=data["reply"], comment_id=comment.id, user_id=user.id, blog_id=blog.id)

                        db.session.add(new_reply)

                        db.session.commit()
                        
                        return jsonify({"Message": "Replied"}), 201
                    
                    return jsonify({"error": "No comment"}), 200
                
                return jsonify({"error": "No blog"}), 200
            
            return jsonify({"error": "No user"}), 200
        except Exception as e:
            return jsonify({"Error": str(e)}), 500



@bp.route("/reply-reply/<int:comment_id>/<int:blog_id>/<int:id>", methods=["POST"])
@jwt_required()
def reply_reply(comment_id: int, blog_id: int, id: int) -> int:
    if request.method == 'POST':

        data = request.get_json()
        user_id = get_jwt_identity()

        if data:
            user = User.query.get(user_id)
            blog = Blog.query.get(blog_id)
            comment = Comment.query.get(comment_id)

            if user:
                if blog:
                    if comment:
                        reply = Reply.query.get(id)
                        if reply:
                            try:
                                reply_reply = Reply(
                                    replies=data['reply'],
                                    comment_id=comment.id,
                                    blog_id=blog.id,
                                    user_id=user.id,
                                    parent_reply_id=reply.id
                                )

                                db.session.add(reply_reply)
                                db.session.commit()
                            except Exception as e:
                                db.session.rollback()
                                return jsonify({"error": str(e)}), 500
                            else:
                                return jsonify({"Message": "Reply replied successfully."}), 201
                            
                        return jsonify({"error": "No reply found."}), 200
                    
                    return jsonify({"error": "No comment found."}), 200
                
                return jsonify({"error": "No blog found."}), 200
            
            return jsonify({"error": "No user found."}), 200
        
        return jsonify({"error": "Replu required."}), 200


@bp.route("/delete-reply/<int:reply_id>", methods=["DELETE"])
@jwt_required()
def delete_reply(reply_id: int) -> int:
    if request.method == "DELETE":
        user = get_jwt_identity()
        try:
            reply = Reply.query.filter_by(id=reply_id).first_or_404()
            
            if reply:
                if int(user) == reply.user_id:
                    db.session.delete(reply)

                    db.session.commit()

                    return jsonify({"Message": "Reply successfully deleted."}), 200
                
                return jsonify({"error": "Can't delete a reply you didn't make. "}), 200
            
            return jsonify("No reply found."), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500



@bp.route("/view-reply")
@rate_limt(MAX_REQUEST=3)
def view_reply():
    replies = Reply.query.all()

    return jsonify({"Replies": [{
        "Reply": reply.replies,
        "Comment": reply.comments.content,
        "Comment user": reply.comments.users.username,
        "Blog": reply.comments.blogs.title,
        "User": reply.users.username
    } for reply in replies]}), 200


@bp.route("/view-replies")
@rate_limt(MAX_REQUEST=3)
def view_replies():
    comments = Comment.query.all()

    return jsonify({
        "Interactions": [{
            "Blog": comment.blogs.title,
            "Comment user's name": comment.users.username,
            "Comment": comment.content,
            "Replies interactions": [serialize_replies(r) for r in comment.replies if r.parent_reply_id is None]
        } for comment in comments]
    }), 200



@bp.route("/like/blog/<int:id>", methods=["POST"])
@jwt_required()
def like_blog(id: int) -> int:
    if request.method == "POST":
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()
        blog = Blog.query.filter_by(id=id).first()

        try:
            if user:
                if blog:
                    if Like.query.filter_by(user_id=user.id, blog_id=blog.id).first():
                        return jsonify({"error": "Already liked this blog."})

                    new_like = Like(user_id=user.id, blog_id=blog.id)

                    db.session.add(new_like)
                    db.session.commit()

                    return jsonify({"Message": "Liked Blog."}), 200
                
                return jsonify({"error": "No blog found"}), 200

            return jsonify({"error": "No user found."}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        


@bp.route("/like/comment/<int:id>", methods=["POST"])
@jwt_required()
def like_comment(id: int) -> int:
    if request.method == "POST":
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()
        comment = Comment.query.filter_by(id=id).first()

        try:
            if user:
                if comment:
                    if Like.query.filter_by(user_id=user.id, comment_id=comment.id).first():
                        return jsonify({"error": "Already liked this comment."})
                    new_like = Like(user_id=user.id, comment_id=comment.id)

                    db.session.add(new_like)
                    db.session.commit()

                    return jsonify({"Message": "Liked Comment."}), 200
                return jsonify({"error": "No comment found"}), 200

            return jsonify({"error": "No user found."}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        


@bp.route("/like/reply/<int:id>", methods=["POST"])
@jwt_required()
def like_reply(id: int) -> int:
    if request.method == "POST":
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()
        reply = Reply.query.filter_by(id=id).first()

        try:
            if user:
                if reply:
                    if Like.query.filter_by(user_id=user.id, reply_id=reply.id).first():
                        return jsonify({"error": "Already liked this reply."})
                    new_like = Like(user_id=user.id, reply_id=reply.id)

                    db.session.add(new_like)
                    db.session.commit()

                    return jsonify({"Message": "Liked Reply."}), 200
                
                return jsonify({"error": "No reply found"}), 200

            return jsonify({"error": "No user found."}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    

@bp.route("/delete-likes/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_likes(id: int) -> int:
    if request.method == "DELETE":
        likes = Like.query.filter_by(id=id).first()
        user = get_jwt_identity()
        try:
            if likes:
                if int(user) == likes.user_id:
                    db.session.delete(likes)

                    db.session.commit()
                    return jsonify({"Message": "Deleted"}), 200
                
                return jsonify({"error": "Cannot delete a like you didn't make."}), 200
            
            return jsonify({"error": "No likes."}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    

@bp.route("/search", methods=["GET"])
@rate_limt(MAX_REQUEST=3, BANNED_TIME=1)
@cache
def search_blog():
    author = request.args.get("a")
    title = request.args.get("q")
    date = request.args.get("p")
    category = request.args.get("c")
    tags = request.args.get("t")

    
    if title and author and category:
        blogs = Blog.query.filter_by(title=title, category=category, author=author).all()

        if blogs:
            try:
                return jsonify({
                    "Blog": [{
                        "Full Query": f"{title} | {category} | {author}",
                        "results": [{
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Interactions": [{
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tags": [tag.name for tag in blog.tags],
                            "Published date": blog.published_date
                        } for blog in blogs],
                    "Message": f"These are all the results pertaining to your search query '{title} || {category} || {author}'."
                    }]
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"Message": "No content with such found"}), 200
        

    elif title:
        blogs = Blog.query.filter_by(title=title).all()

        if blogs:
            try:
                return jsonify({
                    "Blog": [{
                        "q": title,
                        "results": [{
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Interactions": [{
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tags": [tag.name for tag in blog.tags],
                            "Published date": blog.published_date
                        } for blog in blogs],
                    "Message": f"These are all the results pertaining to your search query '{title}'."
                    }]
                    
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"Message": "No content with such title"}), 200
    
    elif tags:
       tag = Tag.query.filter_by(name=tags).first()
       
       if tag:
            try:
                return jsonify({
                    "Blog": [{
                        "t": tags,
                        "result": [{
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Published date": blog.published_date,
                            "Interactions": [{
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tag": [tag.name for tag in blog.tags],
                        } for blog in tag.blogs],
                    "Message": f"These are all the results pertaining to your search query '{tags}'."
                    }]
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
       else:
            return jsonify({"Message": "No content with such tag"}), 200
        
    elif category:
        blogs = Blog.query.filter_by(category=category).all()

        if blogs:
            try:
                return jsonify({
                    "Blog": [{
                        "c": category,
                        "results": [{
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Interactions": [{
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tags": [tag.name for tag in blog.tags],
                            "Published date": blog.published_date
                        } for blog in blogs],
                    "Message": f"These are all the results pertaining to your search query '{category}'."
                    }]
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"Message": "No content with such category"}), 200
    

    elif author:
        blogs = Blog.query.filter_by(author=author).all()

        if blogs:
            try:
                return jsonify({
                    "Blog": [{
                        "a": author,
                        "results": [{
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Interactions": [{
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tags": [tag.name for tag in blog.tags],
                            "Published date": blog.published_date
                        } for blog in blogs],
                    "Message": f"These are all the results pertaining to your search query '{author}'."
                    }]
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"Message": "No content by such author"}), 200
        
    elif date:
        blogs = Blog.query.all()

        try:
            result = [{
                "p": date,
                "results": [{
                    "Title": blog.title,
                    "Category": blog.category,
                    "Content": blog.content,
                    "Blog Likes": get_blog_likes(blog),
                    "Author": blog.author,
                    "Interactions": [{
                        "Comment": comment.content,
                        "Comment username": comment.users.username,
                        "Comment Likes": get_comment_likes(comment),
                        "Replycontent": [{
                            "Reply": reply.replies,
                            "Reply username": reply.users.username,
                            "Reply Likes": get_reply_likes(reply),
                            } for reply in comment.replies]
                    }for comment in blog.comments],
                    "Tags": [tag.name for tag in blog.tags],
                    "Published date": blog.published_date
                } for blog in blogs if blog.published_date.strftime("%Y-%m-%d") == date],
                "Message": f"These are all the results pertaining to your search query '{date}'."
            }]
            
            if result[0]['results']:
                return jsonify({"Blog": result}),200
            else:
                return jsonify({"Message": "No content with such date"}), 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
        
    else:
        return jsonify({
            "Notice": "Missing search parameters.",
            "How to query the API": [{
                "q": "for blog title query; assuming you know the title of the blog",
                "t": "query by tag",
                "c": "query by category",
                "a": "query by author",
                "p": "query by published date. NOTE: date must follow this standard (yy-mm-dd) e.g (2025-06-12)"
            }],
            "Full query": "You can add q,c,a query parameter for specific query."
        }), 400
    

@bp.route("/user-profile", methods=["GET"])
@jwt_required()
def profile():
    
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user:
        return jsonify({
            "Username": user.username,
            "Email": user.email,
            "Users activities": [{
                "Blog commented": blog.blogs.title,
                "Blog's comments replied": [reply.blogs.title for reply in user.replies]
            } for blog in user.comments],
        }), 200
    
    return jsonify({"error": "No user found"}), 200



@bp.route('/logout', methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()['jti']

    try:
        invalid_token = InvalidToken(jti=jti)

        db.session.add(invalid_token)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    else:
        db.session.commit()
        return jsonify({"Message": "Logged out successfully."}), 200   