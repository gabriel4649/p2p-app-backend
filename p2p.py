#!/usr/bin/python

from flask import Flask, make_response, jsonify, request, abort, url_for, \
    render_template
from flask.ext.httpauth import HTTPBasicAuth
from flask.ext.pymongo import PyMongo
from flask.ext.testing import TestCase
from flask.ext.uploads import UploadSet, IMAGES, configure_uploads 
from md5 import md5
from bson.json_util import dumps
from urlparse import urlparse
from datetime import date

import code, os, bson

app = Flask(__name__, static_url_path='')
auth = HTTPBasicAuth()
UPLOADS_DEFAULT_DEST = os.getcwd()+os.sep+'/uploads/'
app.config['UPLOADS_DEFAULT_DEST'] = UPLOADS_DEFAULT_DEST
UPLOADS_DEFAULT_URL = '/uploads'
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)



salt = "thisCode1337Safe"

MONGO_URL = os.environ.get('MONGOHQ_URL')
 
if MONGO_URL:
    # Connect to the Heroku Mongo server
    url = urlparse(MONGO_URL)
    app.config['HEROKU_HOST'] = url.hostname
    app.config['HEROKU_PORT'] = url.port
    app.config['MONGO_USERNAME'] = url.username
    app.config['MONGO_PASSWORD'] = url.password
    app.config['HEROKU_DBNAME'] = MONGO_URL.split('/')[-1]
    mongo = PyMongo(app, config_prefix='HEROKU')

else:
    # Connect to MongoDB with the defaults
    mongo = PyMongo(app)

auth = HTTPBasicAuth()

@app.route("/")
def index():
    return render_template("index.html")

@auth.get_password
def get_password(username):
    user = mongo.db.users.find_one({"username":username})
    return user['password']

@app.route("/test_auth")
@auth.login_required
def test_auth():
    """
    Call this method just to see if auth token works.
    """
    return "ok", 200

@auth.hash_password
def hash_pw(password):
    return md5(password + salt).hexdigest()

@auth.error_handler
def unauthorized():
    return make_response(jsonify( { 'error': 'Unauthorized access' } ), 401)

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify( { 'error': 'Not found' } ), 404)

@app.route("/questions", methods=['GET'])
def get_recent_questions():
    questions = mongo.db.questions.find().sort('$natural',-1).limit(10)
    list = []
    for q in questions:
     tmp = {}
     tmp['posted-epoch-time'] = q['_id'].generation_time
     tmp['id'] = str(q['_id'])
     tmp['title'] = q['title']
     tmp['tags'] = q['tags']
     tmp['submitter'] = q['submitter']
     tmp['votes'] = q['votes']
     tmp['number_of_answers'] = mongo.db.answers.find({"question_id":q['_id']}).count()
     
     list.append(tmp)
    return dumps(list), 201

@app.route('/register', methods=["POST"])
def register():
    if not request.json:
        abort(400)

    data_fields = ("username", "password", "email")
    if not all(d in request.json for d in data_fields):
        abort(400)

    pw_hash = md5(request.json['password'] + salt).hexdigest()
    user = {
        'username'  : request.json['username'],
        'email'     : request.json['email'],
        'password'  : pw_hash
    }

    mongo.db.users.insert(user)

    return make_response(jsonify( { 'success': 'ok!' } ), 201)

# This function returns the profile of a specific user
# Points, Image
@app.route('/user', methods=["GET"])
@auth.login_required
def get_profile():
    user = mongo.db.users.find_one({"username":auth.username()})
    profile = {}
    profile['username'] = user['username']
    profile['number_of_questions'] = mongo.db.questions.find(
                                        {"submitter":user['username']}).count()
    profile['number_of_answers'] = mongo.db.answers.find(
                                        {"submitter":user['username']}).count()
    return dumps(profile), 201

@app.route('/user/question', methods=["GET"])
@auth.login_required
def get_questions_for_user():
    question = {}
    question = mongo.db.questions.find({"submitter":auth.username()})  
    return dumps(question), 201

@app.route('/user/answer', methods=["GET"])
@auth.login_required
def get_answer_for_user():
    answer = mongo.db.answers.find({"submitter":auth.username()})
    return dumps(answer), 201

#This function deals with image uploading. Not Complete!
@app.route('/upload', methods=['GET', 'POST'])
@auth.login_required
def upload():
    if request.method == 'POST' and 'photo' in request.files:
        filename = photos.save(request.files['photo'])
        print filename

    image = {
             'username':auth.username(),
             'img_uri': 'uploads/photos/'+filename
             }
    mongo.db.images.insert(image)
    
    print UPLOADS_DEFAULT_DEST
    return "Successfully uploaded", 201

@app.route('/questions/<ObjectId:question_id>', methods=["GET"])
def get_question(question_id):
    question = mongo.db.questions.find_one(question_id)

    question['posted-epoch-time'] = question['_id'].generation_time
    question['_id'] = str(question['_id'])
    ans = mongo.db.answers.find({"question_id":question_id})
    list= []
    for a in ans:
        tmp = {}
        tmp['author'] = a['submitter']
        tmp['answer'] = a['content']
        tmp['votes'] = a['votes']
        tmp['posted-epoch-time'] = a['_id'].generation_time
        list.append(tmp)
    question['answers'] = list
    return dumps(question), 201

@app.route('/questions/<ObjectId:question_id>', methods=["PUT"])
@auth.login_required
def add_answser(question_id):
    answer = {
              'question_id':question_id,
              'content':request.json['answer'],
              'submitter':auth.username(),
              'votes':0     
              }
    mongo.db.answers.insert(answer)
    return "ok", 200

@app.route('/questions', methods=['POST'])
@auth.login_required
def add_question():
    print request.json
    data_fields = ("title", "detailed", "tags")
    if not all(d in request.json for d in data_fields):
        abort(400)

    question = {
        'votes': '',
        'title': request.json['title'],
        'tags': request.json['tags'],
        'detailed': request.json['detailed'],
        'submitter': auth.username(),
        'images': {},
        'answers' : {}

    }

    id = str(mongo.db.questions.insert(question))
    question['uri'] = url_for('get_question', question_id = id, \
                              _external = True)

    return dumps( { 'question': question }), 201

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
