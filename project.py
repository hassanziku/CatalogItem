from Database_setup import Base, Categories, Items, Users
from flask import session as login_session
import random
import string, datetime
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
import datetime
from flask import Flask, render_template, url_for, request, jsonify, flash, redirect


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item calatog"
engine = create_engine('sqlite:///categories.db')
Base.metadata.bind = engine

app = Flask(__name__)





def createUser(login_session):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    newUser = Users(name=login_session['username'],
                    email=login_session['email'],
                    picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(Users).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    user = session.query(Users).filter_by(id=user_id).first()
    return user


def getUserId(email):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    try:
        user = session.query(Users).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/catalog.json/')
def listItemsJSON():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    cats = session.query(Categories).all()
    categ = [j.serialize for j in cats]
    for j in range(len(categ)):
        items = [i.serialize for i in session.query(Items).filter_by(category_id=categ[j]["id"]).all()]
        if items:
            categ[j]["Item"] = items
    return jsonify(Category=categ)


@app.route('/<string:item_name>/singleItem.json/')
def listItemJSON(item_name):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    items = session.query(Items).filter_by(name=item_name).all()
    return jsonify(items=[i.serialize for i in items])


@app.route('/<string:category_name>/singleCategory.json/')
def listcategoryJSON(category_name):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    cat = session.query(Categories).filter_by(name=category_name).first()
    items = session.query(Items).filter_by(category_id=cat.id).all()
    return jsonify(items=[i.serialize for i in items])


@app.route('/login')
def showLogin():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    state = ''.join(random.choice
                    (string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps
                                 ('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = getUserId(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id
    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ''' " style = "width: 300px; height: 300px;border-radius: 150px;
                -webkit-border-radius: 150px;-moz-border-radius: 150px;"> '''
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


@app.route('/')
def listcategories():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    allcategories = session.query(Categories).all()
    items = session.query(Items).order_by(Items.datee.desc()).limit(10).all()
    if 'username' not in login_session:
        return render_template('Home.html', allcategories=allcategories,
                               items=items)
    else:
        return render_template('HomeLoggedIn.html',
                               allcategories=allcategories, items=items)


@app.route('/catalog/<string:category_name>/items/')
def listItems(category_name):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    allcategories = session.query(Categories).all()
    categor = session.query(Categories).filter_by(name=category_name).first()
    allitems = session.query(Items).filter_by(category_id=categor.id).all()
    if 'username' not in login_session:
        return render_template('snowboardingItems.html',
                               allcategories=allcategories,
                               categor=categor, allitems=allitems)
    else:
        return render_template('itemsLoggedIn.html',
                               allcategories=allcategories, categor=categor,
                               allitems=allitems)


@app.route('/catalog/<string:category_name>/<string:item_name>/')
def listdesc(category_name, item_name):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    categor = session.query(Categories).filter_by(name=category_name).first()
    item = session.query(Items).filter_by(name=item_name).first()
    if 'username' not in login_session:
        return render_template('snowboardingSnowboard.html', categor=categor,
                               item=item)
    else:
        return render_template('descLoggedIn.html', categor=categor,
                               item=item)


@app.route('/catalog/add/', methods=['GET', 'POST'])
def addItem():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    categories = session.query(Categories).all()
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newItem = Items(name=request.form['title'], description=request.form
                        ['description'],
                        categories = session.query(Categories).filter_by(name=request.form['catego']).first(),
                        datee=datetime.datetime.now(),
                        user_id=login_session['user_id'])
        session.add(newItem)
        session.commit()
        return redirect(url_for('listcategories'))
    else:
        return render_template('addItemm.html', categories=categories)


@app.route('/catalog/<string:category_name>/<string:item_name>/edit/',
           methods=['GET', 'POST'])
def editItem(item_name, category_name):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    edititem = session.query(Items).filter_by(name=item_name).first()
    creator = getUserInfo(edititem.user_id)
    user = getUserInfo(login_session['user_id'])
    if 'username' not in login_session:
        return redirect('/login')
    if creator and creator.id != login_session['user_id']:
        flash("you are not authorised to delete the item")
        return redirect (url_for('listItems', category_name = category_name))
    if request.method == 'POST':
        if request.form['title']:
            edititem.name = request.form['title']
        if request.form['description']:
            edititem.description = request.form['description']
        if request.form['category']:
            cat = session.query(Categories).filter_by(name=request.form['category']).first()
            edititem.categories_id = cat.id
        session.add(edititem)
        session.commit()
        return redirect(url_for('listItems', category_name=category_name))
    else:
        return render_template('editCategory.html',
                               category_name=category_name, i=edititem)


@app.route('/catalog/<string:category_name>/<string:item_name>/delete/', methods=['GET', 'POST'])
def delItem(item_name, category_name):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    delitem = session.query(Items).filter_by(name=item_name).first()
    creator = getUserInfo(delitem.user_id)
    user = getUserInfo(login_session['user_id'])
    if 'username' not in login_session:
        return redirect('/login')
    if creator and creator.id != login_session['user_id']:
        flash("you are not authorised to delete the item")
        return redirect (url_for('listItems', category_name = category_name))
    if request.method == 'POST':
        session.delete(delitem)
        session.commit()
        return redirect(url_for('listItems', category_name=category_name))
    else:
        return render_template('delete.html', category_name=category_name,
                               i=delitem)


@app.route('/gdisconnect')
def Gdisconnect():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = redirect(url_for('listcategories'))
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


if __name__ == '__main__':
    app.debug = True
    app.secret_key = 'super_secret_key'
    app.run(host='0.0.0.0', port=5000)
