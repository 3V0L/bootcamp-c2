from flask import jsonify, Blueprint, request, Flask
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token, get_jwt_identity
)
import datetime
from dateutil.relativedelta import relativedelta
from api import create_app, db
from api.models.validate import HelloBooks
from api.models.book import Books
from api.models.user import User


class Borrow(db.Model):
    '''Class for borrowing books'''

    __tablename__ = 'borrow'
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(60))
    borrow_date = db.Column(db.String(11))
    due_date = db.Column(db.String(11))
    book_id = db.Column(db.String(20))
    date_returned = db.Column(db.String(11))

    @staticmethod
    def check_if_user_has_borrowed(user_email):
        '''Check if the user has borrowed a book'''
        if Borrow().query.filter_by(user_email=user_email).count() < 1:
            return jsonify({"message": 'This user has not borrowed any books yet'}), 200

    def borrow_book(self, book_id, user_email, borrow_date, due_date, return_date):
        '''Function to borrow a book'''
        book = Books().query.filter_by(id=book_id).first()
        books_not_returned = Borrow().query.filter_by(
            user_email=user_email, date_returned=None).count()
        Books().check_if_book_exists(book_id)
        if HelloBooks().date_validate(due_date) is False:
            return jsonify({"message": "Please enter a valid date"}), 401
        '''Convert dates for later comparison'''
        borrow_time = datetime.datetime.today() + relativedelta(days=40)
        due = datetime.datetime.strptime(due_date, "%d/%m/%Y")
        borrow_period = datetime.datetime.strptime(
            borrow_time.strftime("%d/%m/%Y"), "%d/%m/%Y")
        '''End of date formating'''
        if book.copies < 1:
            return jsonify(
                {"message": 'All copies of %s have been borrowed.' % book.title})
        if books_not_returned > 4:
            return jsonify(
                {"message": 'you have borrowed 5 books. Please return 1 to be able to borrow another'}), 401
        if due > borrow_period:
            return jsonify(
                {"message": 'Please select a return date that is less than or equal to 40 days.'}), 401
        else:
            data = Borrow(
                user_email=user_email,
                borrow_date=borrow_date,
                due_date=due_date,
                date_returned=return_date,
                book_id=book_id
            )
            book.copies = book.copies - 1
            book.date_modified = datetime.datetime.now()
            db.session.add(data)
            db.session.commit()
            borrow = Borrow().query.order_by(Borrow.id.desc()).first()
            return jsonify(
                {'message': 'You have borrowed the book %s due on %s. Borrow ID: #%s'
                            % (book.title, due_date, borrow.id)}), 201

    def return_book(self, borrow_id, user_email, return_date):
        '''function to return a book'''
        if Borrow().query.filter_by(id=borrow_id).count() is 0:
            return jsonify({"message": "There is no book borrowed under this id"}), 404
        borrow = Borrow().query.filter_by(id=borrow_id).first()
        book = Books().query.filter_by(id=borrow.book_id).first()
        if borrow.date_returned is None:
            if borrow.user_email == user_email:
                borrow.date_returned = return_date
                book.copies = book.copies + 1
                book.date_modified = datetime.datetime.now()
                db.session.commit()
                return jsonify({"message": "The book %s has been returned" % book.title}), 201
            return jsonify({"message": "You did not borrow this book"}), 401
        return jsonify({"message": "This book has been returned already"}), 401

    def borrowing_history(self, user_email, page, per_page):
        '''Function to retrieve a users full borrowing history'''
        self.check_if_user_has_borrowed(user_email)
        borrow_list = []
        history = Borrow().query.filter_by(user_email=user_email).paginate(
            page,
            per_page,
            error_out=True)
        for item in history.items:
            book = Books().query.filter_by(id=item.book_id).first()
            user = User().query.filter_by(email=user_email).first()
            borrowed = self.borrow_dictionary(item, book, user)
            borrow_list.append(borrowed)
        return jsonify(borrow_list), 200

    def books_not_returned(self, user_email):
        '''Function to retrieve the books currently in the possession of the user'''
        self.check_if_user_has_borrowed(user_email)
        borrow_list = []
        history = Borrow().query.filter_by(user_email=user_email)
        for item in history:
            book = Books().query.filter_by(id=item.book_id).first()
            user = User().query.filter_by(email=user_email).first()
            borrowed = self.borrow_dictionary(item, book, user)
            if item.date_returned is None:
                borrow_list.append(borrowed)
        if len(borrow_list) < 1:
            return jsonify({"message": "All books have been returned."}), 200
        return jsonify(borrow_list), 200

    def books_currently_out(self, page, per_page):
        '''Function to retrieve a list of all books that are currently borrowed'''
        User().check_user_is_admin()
        if Borrow().query.all() is None:
            return jsonify({"message": "No books have been borrowed yet."}), 204
        currently_out_list = []
        borrowed = Borrow().query.order_by(Borrow.id.asc()).paginate(
            page,
            per_page,
            error_out=True)
        for item in borrowed.items:
            book = Books().query.filter_by(id=item.book_id).first()
            user = User().query.filter_by(email=item.user_email).first()
            borrowed_dict = self.borrow_dictionary(item, book, user)
            if item.date_returned is None:
                currently_out_list.append(borrowed_dict)
        return jsonify(currently_out_list), 200
        
    def borrow_dictionary(self, item, book, user):
        '''Return the dictionary for borrowing details'''
        return {
            "borrow_id": item.id,
            "book_title": book.title,
            "isbn": book.isbn,
            "username": user.username,
            "borrow_date": item.borrow_date,
            "due_date": item.due_date,
            "date_returned": item.date_returned,
        }