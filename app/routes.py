from flask import Blueprint, jsonify, request, abort, url_for, send_from_directory, current_app, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, get_jwt_identity, get_jwt, jwt_required
from werkzeug.utils import secure_filename
import uuid
from sqlalchemy import event

import os
import json
from itertools import zip_longest

from .models import db, Blog, Tag, User, Comment, Reply, Like, InvalidToken, Follow, Image
from .helper import get_blog_likes, serialize_replies, get_comment_likes, get_reply_likes, cache, get_user, rate_limt, validate_name, user_id_int, is_following, img_extension_finder, valid_image_ext

bp = Blueprint("bp", __name__)

@bp.route("/")
def home():
    return render_template("index.html"), 200

@bp.route("/blogs", methods=["POST"])
@jwt_required()
def post_blog():
    """This route content type is also not application/json. It is multipart/form-data."""
    if request.method == "POST":
        json_data = request.form.get("data")
        image = request.files.get("image")



        if json_data or json_data is not None:
            data = json.loads(json_data)

            title = data.get("title")
            content = data.get("content")
            category = data.get("category")
            tag = data.get("tag")
            image_name = data.get("image_name")

            try:
                user_id = get_jwt_identity()
                if not user_id:
                    abort(401)

                user = get_user(user_id)
                if not user:
                    return jsonify({"error": "No user found!."}), 500
                
                if not image:
                    new_blog = Blog(title=title, content=content, category=category, author=user.username, user_id=user_id)
                    for i in range(len(tag)):
                        new_tag = Tag(name=tag[i])
                        db.session.add(new_tag)
                        new_blog.tags.append(new_tag)
                
                    db.session.add(new_blog)

                else:

                    #Check if the image name is already in the database.
                    if secure_filename(image.filename) in [
                        img.img_file_path for img in Image.query.all()
                    ] or secure_filename(image.filename) in current_app.config["UPLOAD_PATH"]:
                        unique_str = str(uuid.uuid4())[:8]
                        image.filename = f"{unique_str}_{image.filename}"


                    #Handles the uplaoding of the image
                    img_filename = secure_filename(image.filename)

                    img_etx = img_extension_finder(img_filename)

                    if not img_etx:
                        return jsonify({"error": "Upload a valid image."}), 400
                    
                    if not valid_image_ext(img_etx.lower()):
                        return jsonify({"error": "Invalid image format. Please upload a valid image."}), 400
                    
                    image.save(os.path.join(current_app.config["UPLOAD_PATH"], img_filename))

                    new_blog = Blog(title=title, content=content, category=category, author=user.username, user_id=user_id)

                    for i in range(len(tag)):
                        new_tag = Tag(name=tag[i])
                        db.session.add(new_tag)
                        new_blog.tags.append(new_tag)
                    

                    
                    new_image = Image(img_name=image_name, img_file_path=img_filename)
                    db.session.add(new_image)
                    new_blog.images.append(new_image)

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
    page = request.args.get("page", 1, type=int)
    per_page = 5
    blogs = Blog.query.paginate(page=page, per_page=per_page, error_out=False)

    next_url = url_for("bp.view_blogs", page=blogs.next_num, per_page=per_page) if blogs.has_next else None
    prev_url = url_for("bp.view_blogs", page=blogs.prev_num, per_page=per_page) if blogs.has_prev else None

    return jsonify({
        "Page": blogs.page,
        "Per_page": per_page,
        "Total_ Pages": blogs.pages,
        "Has_next": blogs.has_next,
        "Has_prev": blogs.has_prev,
        "Next": next_url,
        "Prev": prev_url,
        "Blogs": [{
            "id": blog.id,
            "Title": blog.title,
            "Content": blog.content,
            "Category": blog.category,
            "Blog Likes": get_blog_likes(blog),
            "Author": blog.author,
            "Author Id": blog.user_id,
            "Images": [
                url_for("bp.serve_images", filename=image.img_file_path, _external=True) for image in blog.images
            ],
            "Interactions": [{
                "id": comment.id,
                "Comment": comment.content,
                "comment user id": comment.users.id,
                "Comment user's name": comment.users.username,
                "Comment Likes": get_comment_likes(comment),
                "ReplyContent": [{
                    "id": reply.id,
                    "Reply": reply.replies,
                    "Reply user id": reply.users.id,
                    "Reply user's name": reply.users.username,
                    "Reply Likes": get_reply_likes(reply)
                } for reply in comment.replies]
            } for comment in blog.comments],
            "Date Pub": blog.published_date.strftime("%Y-%m-%d"),
            "Tags": [tag.name for tag in blog.tags]
        } for blog in blogs.items]
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
    """This route content type is no longer application/json rather it is multipart/form-data"""
    if request.method == "POST":
        json_data = request.form.get("data")
        image = request.files.get("image")

        if json_data and json_data is not None:
            try:
                data = json.loads(json_data)

                username = data.get("username")
                email = data.get("email")
                password = data.get("password")

                user = User.query.filter_by(email=email).first()
                if user:
                    return jsonify({"error": "User already exists."})
                
                if not image:
                    #Incase user doesn't want to use a profile picture immediately.
                    new_user = User(username=username, email=email, password=generate_password_hash(password))

                    db.session.add(new_user)
                else:
                    #Checks if filepath already exists in the database
                    if secure_filename(image.filename) in [
                        img.profile_image for img in User.query.all()
                    ]:
                        unique_id = str(uuid.uuid4())[:8]

                        image.filename = f"{unique_id}_{image.filename}"

                    #Handles file uploads
                    img_filename = secure_filename(image.filename)

                    if img_filename:
                        file_ext = img_extension_finder(img_filename)

                        if not valid_image_ext(file_ext.lower()):
                            return jsonify({"error": "File type not supported. Please upload a valid image"}), 400
                        
                        image.save(os.path.join(current_app.config["UPLOAD_PATH"], img_filename))

                        new_user = User(username=username, email=email, password=generate_password_hash(password), profile_image=img_filename)
                        db.session.add(new_user)
                        
            except Exception as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 500
            else:
                db.session.commit()
                return jsonify({"Message": "User added successfully."}), 201
            
        return jsonify({"error": "Username, email and password field is required."}), 400


@bp.route("/login", methods=["POST"])
def login():
    if request.method == "POST":
        data = request.get_json()

        user = User.query.filter_by(username=data["username"]).first()

        try:
            if user:
                if data is None or not data:
                    return jsonify({"error": "username and password fields cannot be empty."}), 400
                
                if check_password_hash(user.password, data["password"]):
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
@jwt_required()
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
@jwt_required()
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

    page = request.args.get("page", 1, type=int)
    per_page = 5

    if title and author and category:
        blogs = Blog.query.filter(Blog.title.ilike(title), Blog.author.ilike(author), Blog.category.ilike(category)).paginate(page=page, per_page=per_page, error_out=False)

        if blogs:
            
            next_url = url_for("bp.search_blog", page=blogs.next_num, per_page=per_page) if blogs.has_next else None
            prev_url = url_for("bp.search_blog", page=blogs.prev_num, per_page=per_page) if blogs.has_prev else None
            try:
                return jsonify({
                    "Page": blogs.page,
                    "Per_page": per_page,
                    "Total blogs": blogs.total,
                    "Next": next_url,
                    "Prev": prev_url,
                    "Blog": [{
                        "Full Query": f"{title} | {category} | {author}",
                        "results": [{
                            "Id": blog.id,
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Interactions": [{
                                "Comment Id": comment.id,
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply Id": reply.id,
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tags": [tag.name for tag in blog.tags],
                            "Published date": blog.published_date
                        } for blog in blogs.items],
                    "Message": f"These are all the results pertaining to your search query '{title} || {category} || {author}'."
                    }]
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"Message": "No content with such found"}), 200
        

    elif title:
        blogs = Blog.query.filter(Blog.title.ilike(f"%{title}%")).paginate(page=page, per_page=per_page, error_out=False)

        next_url = url_for("bp.search_blog", page=blogs.next_num, per_page=per_page) if blogs.has_next else None
        prev_url = url_for("bp.search_blog", page=blogs.prev_num, per_page=per_page) if blogs.has_prev else None

        if blogs:
            try:
                return jsonify({
                    "Page": blogs.page,
                    "Per_page": per_page,
                    "Next": next_url,
                    "Prev": prev_url,
                    "Blog": [{
                        "q": title,
                        "results": [{
                            "Id": blog.id,
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Interactions": [{
                                "Comment Id": comment.id,
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply Id": reply.id,
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tags": [tag.name for tag in blog.tags],
                            "Published date": blog.published_date
                        } for blog in blogs.items],
                    "Message": f"These are all the results pertaining to your search query '{title}'."
                    }]
                    
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"Message": "No content with such title"}), 200
    
    elif tags:
       tag = Tag.query.filter(Tag.name.ilike(f"%{tags}%")).paginate(page=page, per_page=per_page, error_out=False)

       next_url = url_for("bp.search_blog", page=blogs.next_num, per_page=per_page) if tag.has_next else None
       prev_url = url_for("bp.search_blog", page=blogs.prev_num, per_page=per_page) if tag.has_prev else None
       
       if tag:
            try:
                return jsonify({
                    "Page": tag.page,
                    "Next": next_url,
                    "Prev": prev_url,
                    "Blog": [{
                        "t": tags,
                        "result": [{
                            "Id": blog.id,
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Published date": blog.published_date,
                            "Interactions": [{
                                "Comment Id": comment.id,
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply Id": reply.id,
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tag": [tag.name for tag in blog.tags],
                        } for t in tag.items for blog in t.blogs],
                    "Message": f"These are all the results pertaining to your search query '{tags}'."
                    }]
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
       else:
            return jsonify({"Message": "No content with such tag"}), 200
        
    elif category:
        blogs = Blog.query.filter(Blog.category.ilike(f"%{category}%")).paginate(page=page, per_page=per_page, error_out=False)

        next_url = url_for("bp.search_blog", page=blogs.next_num, per_page=per_page) if blogs.has_next else None
        prev_url = url_for("bp.search_blog", page=blogs.prev_num, per_page=per_page) if blogs.has_prev else None

        if blogs:
            try:
                return jsonify({
                    "Page": blogs.page,
                    "Per_page": per_page,
                    "Total content": blogs.total,
                    "Next": next_url,
                    "Prev": prev_url,
                    "Blog": [{
                        "c": category,
                        "results": [{
                            "Id": blog.id,
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Interactions": [{
                                "Comment Id": comment.id,
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply Id": reply.id,
                                    "Reply": reply.replies,
                                    "Reply username": reply.users.username,
                                    "Reply Likes": get_reply_likes(reply),
                                } for reply in comment.replies]
                            }for comment in blog.comments],
                            "Tags": [tag.name for tag in blog.tags],
                            "Published date": blog.published_date
                        } for blog in blogs.items],
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
                            "Id": blog.id,
                            "Title": blog.title,
                            "Category": blog.category,
                            "Content": blog.content,
                            "Blog Likes": get_blog_likes(blog),
                            "Author": blog.author,
                            "Interactions": [{
                                "Comment Id": comment.id,
                                "Comment": comment.content,
                                "Comment username": comment.users.username,
                                "Comment Likes": get_comment_likes(comment),
                                "Replycontent": [{
                                    "Reply Id": reply.id,
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
        blogs = Blog.query.paginate(page=page, per_page=per_page, error_out=False)

        next_url = url_for("bp.search_blog", page=blogs.next_num, per_page=per_page) if blogs.has_next else None
        prev_url = url_for("bp.search_blog", page=blogs.prev_num, per_page=per_page) if blogs.has_prev else None

        try:
            result = [{
                "Page": blogs.page,
                "Next": next_url,
                "Prev": prev_url,
                "p": date,
                "results": [{
                    "Id": blog.id,
                    "Title": blog.title,
                    "Category": blog.category,
                    "Content": blog.content,
                    "Blog Likes": get_blog_likes(blog),
                    "Author": blog.author,
                    "Interactions": [{
                        "Comment Id": comment.id,
                        "Comment": comment.content,
                        "Comment username": comment.users.username,
                        "Comment Likes": get_comment_likes(comment),
                        "Replycontent": [{
                            "Reply Id": reply.id,
                            "Reply": reply.replies,
                            "Reply username": reply.users.username,
                            "Reply Likes": get_reply_likes(reply),
                            } for reply in comment.replies]
                    }for comment in blog.comments],
                    "Tags": [tag.name for tag in blog.tags],
                    "Published date": blog.published_date
                } for blog in blogs.items if blog.published_date.strftime("%Y-%m-%d") == date],
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
    
@bp.route("/serve-images/<filename>")
@jwt_required()
def serve_images(filename):
    """This route serves images to any other routes that requires images."""
    return send_from_directory(current_app.config["UPLOAD_PATH"], filename)


@bp.route("/user-profile/<int:id>", methods=["GET"])
@bp.route("/user-profile", methods=["GET"])
@jwt_required()
def profile(id=None):
    if id:
        user = get_user(id)
        if user is None or not user:
            return jsonify({"error": "User not found. Maybe user has deleted their account."}), 200

        try:

            profile_photo_url = (url_for("bp.serve_images", filename=user.profile_image, _external=True) if user.profile_image else None)

            return jsonify({
                "Username": user.username,
                "Email": user.email,
                "Profile Photo": profile_photo_url,
                "Following": [following.following_user.username for following in user.following.all()],
                "Followers": [follower.follower_user.username for follower in user.followers.all()],
                "Blogs": [{
                "Title": blog.title,
                "Category": blog.category,
                "Content": blog.content,
                "Tag": [tag.name for tag in blog.tags],
                "Blog Likes": get_blog_likes(blog), 
                "Interactions": [{
                    "Comment": comment.content,
                    "Comment Id": comment.id,
                    "Comment username": comment.users.username,
                    "Comment Likes": get_comment_likes(comment),
                    "Comment Reply": [{
                        "Reply Id": reply.id,
                        "Reply": reply.replies,
                        "Reply username": reply.users.username,
                        "Reply Likes": get_reply_likes(reply)
                    } for reply in comment.replies],
                } for comment in blog.comments],
                "Blog date": blog.published_date
            } for blog in user.blogs_posts]
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    user_id = get_jwt_identity()
    if user_id is None or not user_id:
        abort(401)

    user_id = user_id_int(user_id)
    user = get_user(user_id)

    try:
        profile_photo_url = (url_for("bp.serve_images", filename=user.profile_image, _external=True) if user.profile_image else None)

        return jsonify({
            "Username": user.username,
            "Email": user.email,
            "Profile Photo": profile_photo_url,
            "Following": [following.following_user.username for following in user.following.all()],
            "Followers": [follower.follower_user.username for follower in user.followers.all()],
            "Blogs": [{
                "Id": blog.id,
                "Title": blog.title,
                "Category": blog.category,
                "Content": blog.content,
                "Tag": [tag.name for tag in blog.tags],
                "Blog Likes": get_blog_likes(blog), 
                "Interactions": [{
                    "Comment": comment.content,
                    "Comment Id": comment.id,
                    "Comment username": comment.users.username,
                    "Comment Likes": get_comment_likes(comment),
                    "Comment Reply": [{
                        "Reply Id": reply.id,
                        "Reply": reply.replies,
                        "Reply username": reply.users.username,
                        "Reply Likes": get_reply_likes(reply)
                    } for reply in comment.replies],
                } for comment in blog.comments],
                "Blog date": blog.published_date
            } for blog in user.blogs_posts]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/search-author", methods=["GET"])
@jwt_required()
def search_author():
    """The frontend developer is supposed to use the returned id from this route and redirect it to the profile route.
    The query parameter for this route is 'a'."""
    data = request.args.get("a")

    try:
            user_id = get_jwt_identity()

            if user_id is None or not user_id:
                abort(401)

            if data is None or not data:
                return jsonify({"error": "'a' search parameter is required."}), 400
            
            result = validate_name(data)
            
            if not result["valid"]:
                return result["data"], result.get("code", 200)
            
            valid_data = result["data"]

            author = User.query.filter_by(username=valid_data).first()

            if author:
                return jsonify({
                    "id": author.id
                }), 200
            
            return jsonify({"error": "No author or user with such name."}), 200
            
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@bp.route("/password-update", methods=["PATCH"])
@jwt_required()
@rate_limt(MAX_REQUEST=2, BANNED_TIME=43800)
def change_password():
    if request.method == 'PATCH':
        user_id = get_jwt_identity()
        data = request.get_json()

        if user_id is not None:
            user = get_user(int(user_id))

            if not user:
                return jsonify({"error": "No user found."}), 200
            
            if data is None or not data:
                return jsonify({"error": "Old password and new password field is required."}), 200
           
            if check_password_hash(user.password, data["old password"]):
                try:
                    user.password = generate_password_hash(data['new password'])
                except Exception as e:
                    db.session.rollback()
                    return jsonify({"error": str(e)}), 500
                else:
                    db.session.commit()
                    return jsonify({"Message": "Password changed successfully"}), 201
            
            return jsonify({"error": "Incorrect password."}), 200
        
        abort(401)


@bp.route("/username-update", methods=["PATCH"])
@jwt_required()
def change_username():
    if request.method == "PATCH":
        data = request.get_json()

        user_id = get_jwt_identity()

        if user_id is not None:
            user = get_user(int(user_id))

            if not user:
                return jsonify({"error": "User not found."})
            
            if data is None or not data:
                return jsonify({"error": "Username field is required"}), 200
            
            try:
                user.username = data['username']
            except Exception as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 500
            else:
                db.session.commit()
                return jsonify({"Message": "Username changed successfully."}), 201
            
        abort(401)


@bp.route("/update-profile-pic", methods=["PATCH"])
@jwt_required()
def update_profile_pic():
    """This route content-type is not application/json; it is multipart/form-data. Frontend devops take note."""
    image = request.files.get("image")

    try:
        user_id = user_id_int(get_jwt_identity())

        if not user_id:
            abort(401)

        if not image:
            return jsonify({"error": "An image is required. Please try uploading an image."}), 400
        
        #Checks if picture with the same name already exists in the database.
        if secure_filename(image.filename) in [
            img.profile_image for img in User.query.all()
        ]:
            unique_code = str(uuid.uuid4())[:8]
            image.filename = f"{unique_code}_{image.filename}"

        #Handles the updating of profile picture.
        img_filename = secure_filename(image.filename)

        img_ext = img_extension_finder(img_filename)

        if not valid_image_ext(img_ext.lower()):
            return jsonify({"error": "Invalid image format. Please provide a valid image format."}), 400
        
        image.save(os.path.join(current_app.config["UPLOAD_PATH"], img_filename))

        user = get_user(user_id)

        if not user:
            return jsonify({"error": "User can't be found. Something went wrong."}), 500
        
        user.profile_image = img_filename

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    else:
        db.session.commit()

        return jsonify({"Message": "Profile picture updated successfully."}), 201


@bp.route("delete-account", methods=["DELETE"])
@jwt_required()
def delete_account():
    user_id = user_id_int(get_jwt_identity())

    if not user_id:
        abort(401)

    user = get_user(user_id)

    if not user:
        return jsonify({"error": "Something wrong occurred."}), 500
    
    try:
        db.session.delete(user)
        db.session.commit()

        return jsonify({"Message": "Account deleted."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500



@bp.route("/follow/<int:id>", methods=["POST"])
@jwt_required()
def follow(id):
    if request.method == "POST":

        user_id = get_jwt_identity()
        user = get_user(id)

        if user_id is None:
            abort(401)
        if not user:
            return jsonify({"error": "No user found. Maybe such person has deleted their account."}), 200
        
        user_id = user_id_int(user_id)
        
        is_follow = is_following(user_id, user.id)

        if not is_follow:
            try:
                new_follower = Follow(follower_user_id=user_id, followed_user_id=user.id)
                db.session.add(new_follower)
            except Exception as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 500
            else:
                db.session.commit()
                return jsonify({"Message:": "Followed Successfully."}), 200
            
        return is_follow


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
    

@event.listens_for(User, "before_update")
def delete_old_profile_image(mapper, connection, target):
    old = User.query.get(target.id)

    if old and old.profile_image != target.profile_image:
        old_path = old.profile_image_path()

        if old_path and os.path.exists(old_path):
            os.remove(old_path)


@event.listens_for(User, "after_delete")
def delete_profile_picture(mapper, connection, target):
    """Deletes the profile picture path ones the user is deleted."""

    file_path = target.profile_image_path()

    if file_path and os.path.exists(file_path):
        os.remove(file_path)