from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm
from forms import RegisterForm
from forms import LoginForm
from forms import CommentForm

# adding additional imports
from functools import wraps
from flask import abort
from typing import List
from flask_gravatar import Gravatar
import os
import smtplib
import pprint
'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
# type in your secret key here
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# This  configure Flask-Login's Login Manager which is responsible for logging users in
login_manager = LoginManager()
login_manager.init_app(app)


# Creating a user_loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass


# this will use the DB_URI variable if its set otherwise it will use posts.db
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", 'sqlite:///posts.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
# Creating a User table for all your registered users.
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)

    # this creates a relationship between the user and blogpost tables. The back populates
    # indicates that the relationship can be reversed. (users mapping to blogpost can be reversed to blog post mapping
    # to user
    posts = relationship("BlogPost", back_populates="author")
    comment = relationship("Comment", back_populates="commentor")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # author: Mapped[str] = mapped_column(String(250), nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    # you are defining which the column in the parent table that will serve as the foreign key id
    # The mapped_column(Integer,....) shows that the column used as a foreign key is an integer
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))

    # The author creates a relationship to the other table. so you get access to the author, you can write
    # author.name to get access to the 'name' in the other table
    author = relationship("User", back_populates="posts")
    commented_blog = relationship("Comment", back_populates="blog_commentor")


class Comment(db.Model):
    __table_name__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_comment: Mapped[str] = mapped_column(Text, nullable=False)

    # adding a foreign key from the parent table (Users)
    commentor_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    commentor = relationship("User", back_populates="comment")

    # adding a foreign key from blogpost parent table (BlogPost)
    blog_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    blog_commentor = relationship("BlogPost", back_populates="commented_blog")


with app.app_context():
    db.create_all()


# Creating a decorator so that only the admin can get access to a particular url
def admin_only(f):
    @wraps(f)
    def decorated_funtion(*args, **kwargs):
        # if the user id is not 1 then return abort with a 403 error
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_funtion


# Harshing a password to protect the integrity of the password used to log in
@app.route('/register', methods=['GET', 'POST'])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        name = register_form.name.data
        email = register_form.email.data
        password = generate_password_hash(
            register_form.password.data,
            method="pbkdf2:sha256",
            salt_length=8)

        # Checking if the email already exist in the database
        user_exist = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user_exist:
            flash("You've signed up with that email. Login instead!")
            return redirect(url_for('login'))

        new_user = User(
            name=name,
            email=email,
            password=password,)
        db.session.add(new_user)
        db.session.commit()

        # Logining in the new user after he creates a new account
        newbie_user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        login_user(newbie_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=register_form, logged_in=current_user.is_authenticated)


# Getting a user from the database based on their email
@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        email = login_form.email.data
        password = login_form.password.data

        # checking to see if the use exists
        selected_user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if not selected_user:
            flash(f"There is no user with the email {email}")
            return redirect(url_for('login'))
        # checking if the password corresponds
        elif not check_password_hash(selected_user.password, password):
            flash("The password you have entered is incorrect, please try again")
            return redirect(url_for('login'))
        else:
            login_user(user=selected_user)
            return redirect(url_for('get_all_posts',  active_user=selected_user.id))

    return render_template("login.html", form=login_form,
                           logged_in=current_user.is_authenticated,

                           )


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
# @login_required
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    if current_user.is_authenticated:
        active_user = current_user.id
    else:
        active_user = None
    return render_template("index.html", all_posts=posts,
                           logged_in=current_user.is_authenticated,
                           active_user=active_user)


# Allowing logged in users to comment on post
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    blog_comments = db.session.execute(db.select(Comment).where(Comment.blog_id == post_id)).scalars()

    # adding Gravatar images
    gravatar = Gravatar(app,
                        size=100,
                        rating='g',
                        default='retro',
                        force_default=False,
                        force_lower=False,
                        use_ssl=False,
                        base_url=None)

    if comment_form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                user_comment=comment_form.comment.data,
                commentor_id=current_user.id,
                blog_id=requested_post.id,
            )
            db.session.add(new_comment)
            db.session.commit()
            # flash('Your comment has been added successfully')
            return redirect(url_for('show_post', post_id=post_id))
        else:
            if not current_user.is_authenticated:
                flash('You need to be logged in to comment.', 'danger')
                return redirect(url_for('login'))

    return render_template("post.html", post=requested_post, comment_form=comment_form, current_user=current_user,
                           logged_in=current_user.is_authenticated, blog_comments=blog_comments, gravatar=gravatar)


# Making sure that only the admin can create a new post incase someone else manually types the /new-post route
@app.route("/new-post", methods=["GET", "POST"])
# @admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# Creating a function to edit the post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
# @admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# Creating a function for deleting the post. the admin_only makes sure that only the admin can delete a post
@app.route("/delete/<int:post_id>")
# @admin_only
def delete_post(post_id):
    # deleting the comments in the blog
    comments_to_delete = db.session.execute(db.select(Comment).where(Comment.blog_id == post_id)).scalars()
    for comment in comments_to_delete:
        db.session.delete(comment)
    db.session.commit()

    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# # deleting a comment
# @app.route("/delete")
# def delete_comment():


# creating a function for the about page
@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)

#
# # creating a function for the contact page
# @app.route("/contact", methods=["GET", "POST"])
# def contact():
#     return render_template("contact.html", current_user=current_user)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        # Handle form submission here
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        message = request.form.get("message")

        # Type the password and email you want to use to be sending the email message of what was typed in the
        # "Contact Me" section to your email
        personal_email = os.environ.get("personal-blog-email")
        personal_password = os.environ.get("personal-blog-password")
        receiver_email = os.environ.get('personal-receiver-email')

        with smtplib.SMTP("smtp.gmail.com") as connection:
            try:
                connection.starttls()
                connection.login(user=personal_email, password=personal_password)

                connection.sendmail(from_addr=personal_email,
                                    to_addrs=receiver_email,
                                    msg=f"Subject:message from {name}\n\n"
                                        f"Name: {name}\n\n"
                                        f"Email: {email}\n\n"
                                        f"Phone: {phone}\n\n"
                                        f"Message: {message}\n")
                flash('Email message was successfully sent', 200)
                print("Email sent")
            except Exception as e:
                print(e)
                # Example: Print form data
                print(f"Name: {name}, Email: {email}, Phone: {phone}, Message: {message}")

    return render_template("contact.html", current_user=current_user, msg_sent=False)


@app.route('/edit_comment/<int:post_id>/<int:comment_id>', methods=['GET', 'POST'])
def edit_comment(comment_id, post_id):
    comment = Comment.query.get_or_404(comment_id)
    comment_form = CommentForm(
        comment=comment.user_comment
    )
    if comment_form.validate_on_submit():
        comment.user_comment=comment_form.comment.data
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template('edit_comment.html', comment_form=comment_form)


@app.route('/delete_comment/<int:post_id>/<int:comment_id>', methods=['GET', 'POST'])
def delete_comment(comment_id, post_id):
    comment = Comment.query.get_or_404(comment_id)
    print(comment)
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('show_post', post_id=post_id))

if __name__ == "__main__":
    app.run(debug=True, port=5002)
