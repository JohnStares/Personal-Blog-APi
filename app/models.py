from flask_sqlalchemy import SQLAlchemy

from datetime import datetime

db = SQLAlchemy()


tag_blog = db.Table('tag_blog',
    db.Column('blog_id', db.Integer, db.ForeignKey('blog.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
)

class Blog(db.Model):
    __tablename__ = "blog"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    author = db.Column(db.String(50), default="Pythonista. John Stares")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    published_date = db.Column(db.DateTime, default=datetime.today())



    likes = db.relationship('Like', backref='blogs', cascade='all, delete')
    comments = db.relationship('Comment', backref='blogs', cascade='all, delete')
    tags = db.relationship('Tag', secondary=tag_blog, backref='blogs', cascade='all, delete')
    replies = db.relationship('Reply', backref='blogs', cascade='all, delete')

    def __repr__(self):
        return "<Title - {}; Content - {}; Category - {}; Pub date - {};>".format(self.title, self.content, self.category, self.published_date)
    


class Tag(db.Model):
    __tablename__ = "tag"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    tag_date = db.Column(db.DateTime, default=datetime.today())

    
    def __repr__(self):
        return "<Tag - {};>".format(self.name)
    


class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(50), nullable=False)
    date_joined = db.Column(db.DateTime, default=datetime.today())

    likes = db.relationship('Like', backref='users', cascade='all, delete')
    comments = db.relationship('Comment', backref='users', cascade='all, delete')
    replies = db.relationship('Reply', backref='users', cascade='all, delete')
    blogs_posts = db.relationship("Blog", backref="users", cascade='all, delete')


    following = db.relationship("Follow",
        foreign_keys=lambda: [Follow.follower_user_id], 
        back_populates="follower_user", 
        lazy="dynamic", 
        cascade="all, delete-orphan",
    )


    followers = db.relationship("Follow",
        foreign_keys=lambda: [Follow.followed_user_id],
        back_populates="following_user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_commented = db.Column(db.DateTime, default=datetime.today())

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'))

    likes = db.relationship('Like', backref='comments', cascade='all, delete')
    replies = db.relationship('Reply', backref='comments', cascade='all, delete')


    def __repr__(self):
        return "<Blog - {}; Comment - {}; Username - {};>".format(self.blog_id, self.content, self.user_id)
    


class Reply(db.Model):
    __tablename__ = "reply"
    id = db.Column(db.Integer, primary_key=True)
    replies = db.Column(db.Text, nullable=False)
    replies_date = db.Column(db.DateTime, default=datetime.today())


    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'))
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    parent_reply_id = db.Column(db.Integer, db.ForeignKey('reply.id'))

    likes = db.relationship('Like', backref='replies', cascade='all, delete')
    children = db.relationship('Reply', backref=db.backref('parent', remote_side=[id]), cascade='all, delete-orphan')

    def __repr__(self):
        return "<Replies - {}; Comment {};>".format(self.replies, self.comment_id)
    


class Like(db.Model):
    __tablename__ = "like"
    id = db.Column(db.Integer, primary_key=True)
    like = db.Column(db.Integer, default=1, nullable=False)
    published_date = db.Column(db.DateTime, default=datetime.today())

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'))
    reply_id = db.Column(db.Integer, db.ForeignKey('reply.id'))
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'))

    def __repr__(self):
        return "<Like - {}; Username - {}; Comment - {}; Blog - {};>".format(self.like, self.user_id, self.comment, self.blog_id)
    

class Follow(db.Model):
    __tablename__ = "follow"
    id = db.Column(db.Integer, primary_key=True)
    follow = db.Column(db.Integer, default=1, nullable=False)
    follow_date = db.Column(db.DateTime, default=datetime.today())

    follower_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    follower_user = db.relationship("User", foreign_keys=[follower_user_id], back_populates="following")
    following_user = db.relationship("User", foreign_keys=[followed_user_id], back_populates="followers")


class InvalidToken(db.Model):
    __tablename__ = "invalidtoken"
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(100), nullable=False)


    @classmethod
    def is_jti_valid(cls, jti):
        query = cls.query.filter_by(jti=jti).first()

        return bool(query)