""" app/events/views.py """

from functools import wraps
from flask import Flask, request, jsonify, abort, make_response

from . import events
from app.models import Events, User, BlacklistToken

import re


def authorize(f):
# Function to authenticate users while accessing other pages
    @wraps(f)
    def check(*args, **kwargs):
        """Function to check login status"""
        access_token = request.headers.get('Authorization')
        blacklisted = BlacklistToken.query.filter_by(token=access_token).first()
        if not blacklisted:
            try:
                return f(*args, **kwargs)
            except KeyError:
                    response = {"message": "There was an error creating the event, please try again"}
                    return make_response(jsonify(response)), 500
        response = {"message": "Logged out. Please login again!" }
        return make_response(jsonify(response)), 200
            
    return check

def checkToken():
    """Check whether token is blacklisted"""
    access_token = request.headers.get('Authorization')
    blacklisted = BlacklistToken.query.filter_by(token=access_token).first()
    if blacklisted:
        return True
    return False

@events.route('/')
def index():
    """ Render index page """

    return jsonify({"message": "Welcome to Bright Events"})

@events.route('/api/v2/events', methods=['POST', 'GET'])
@events.route('/api/v2/events/page=<int:page>&limit=<int:limit>', methods=['GET'])
@authorize
def create(limit=4, page=1):

    # Get the access token from the header
    auth_header = request.headers.get('Authorization')
    access_token = auth_header

    if access_token:
        # Attempt to decode the token and get the User ID
        user_id = User.decode_token(access_token)
        if not isinstance(user_id, str):
            # Go ahead and handle the request, the user is authenticated

            if request.method == "POST":
                event = request.get_json()
                name=event['name'].strip() 
                category=event['category']
                location=event['location']
                date=event['date']
                description=event['description']

                if not event['name'] or not event['category'] or \
                not event['location'] or not event['date']:
                    # Check whether fields are not empty
                    response = {"message" : "Event details cannot be empty!"}
                    return make_response(jsonify(response)), 400

                if len(event['name'].strip())<5 or not re.match("^[a-zA-Z0-9_ ]*$", event['name'].strip()):
                    response = {"message" : "Event name cannot have special characters!"}
                    return make_response(jsonify(response)), 400

                existing=Events.query.filter_by(name=name).filter_by(category=category).filter_by\
                (created_by=user_id).filter_by(location=location).first()
                if existing:
                    response = {"message" : "A similar event already exists!"}
                    return make_response(jsonify(response)), 302
                try:
                    created_event = Events(
                                    name=name,
                                    category=category,
                                    location=location, 
                                    date=date,
                                    description=description,
                                    created_by = user_id
                                    )
                    created_event.save()
                    response = jsonify({
                        'id': created_event.id,
                        'name' : created_event.name,
                        'category' : created_event.category,
                        'location' : created_event.location,
                        'date' : created_event.date,
                        'description' : created_event.description,
                        'created_by' : created_event.created_by
                    })

                except AttributeError:
                    response = {"message": "There was an error creating the event, please try again"}
                    return make_response(jsonify(response)), 500
                                        
                return make_response(response), 201

            else:
                # GET
                events = Events.query.filter_by(created_by=user_id).paginate(page, per_page = limit, \
                error_out=True).items
                # Query all
                # events = Events.query.paginate(page, per_page = 3, error_out=True).items
                # events = Events.get_all(user_id)
                results = []

                for event in events:
                    obj = {
                        'id': event.id,
                        'name' : event.name,
                        'category' : event.category,
                        'location' : event.location,
                        'date' : event.date,
                        'description' : event.description

                    }
                    results.append(obj)
                return make_response(jsonify(results)), 200
        
        else:
            # user is not legit, so the payload is an error message
            message = user_id
            response = {
                'message': message
            }
            return make_response(jsonify(response)), 401

@events.route('/api/v2/events/<int:event_id>', methods=['GET', 'PUT', 'DELETE'])
@authorize
def event_tasks(event_id):
    # get the access token from the authorization header
    auth_header = request.headers.get('Authorization')
    access_token = auth_header

    if access_token:
        # Get the user id related to this access token
        user_id = User.decode_token(access_token)

        if not isinstance(user_id, str):
            # If the id is not a string(error), we have a user id
            # Get the event with the id specified from the URL (<int:id>)
            event = Events.query.filter_by(id=event_id).first()
            
            # print(event)
            if not event:
                # There is no event with this ID for this User, so
                response = {
                    "message": "Event does not exist!"
                }
                return jsonify(response), 404

            if request.method == "DELETE":
                # delete the event using our delete method
                # Check if event belongs to user
                created_by = event.created_by
                print(created_by)
                if user_id == created_by:
                    event.delete()
                    response = {
                        "message": "event {} deleted".format(event.id)
                    }

                    return jsonify(response), 200
                response = {
                    "message": "You can only delete your own event"
                }
                return jsonify(response), 401

            elif request.method == 'PUT':
                created_by = event.created_by
                print(created_by)
                if user_id == created_by:
                # Obtain the new name of the event from the request data
                    edited = request.get_json()

                    event.name=edited['name']
                    event.category=edited['category']
                    event.location=edited['location']
                    event.date=edited['date']
                    event.description=edited['description']
                    event.save()

                    response = {
                        'id': event.id,
                        'name' : event.name,
                        'category' : event.category,
                        'location' : event.location,
                        'date' : event.date,
                        'description' : event.description
                    }

                    msg = {"message": "Event update successful"}
                    
                    return make_response(jsonify(msg)), 200
                response = {
                    "message": "You can only modify your own event"
                }
                return jsonify(response), 401
            else:
                # Handle GET request, sending back the event to the user
                response = {
                    'id': event.id,
                    'name' : event.name,
                    'category' : event.category,
                    'location' : event.location,
                    'date' : event.date,
                    'description' : event.description
                }
                return make_response(jsonify(response)), 200
        else:
            # user is not legit, so the payload is an error message
            message = user_id
            response = {
                'message': message
            }
            # return an error response, telling the user he is Unauthorized
            return make_response(jsonify(response)), 401

@events.route('/api/v2/event/<event_id>/rsvp', methods=['POST', 'GET'])
def rsvp(event_id):
    """RSVP to an event"""
    # get the access token from the authorization header
    auth_header = request.headers.get('Authorization')
    access_token = auth_header
    if access_token:
        # Get the user id related to this access token
        user_id = User.decode_token(access_token)
        token_status = checkToken()
        if not token_status:
            # User is still logged in; Continue
            if not isinstance(user_id, str):
                # If the id is not a string(error), we have a user id
                # Get the event with the id specified from the URL (<int:id>)
                event = Events.query.filter_by(id=event_id).first()
                if event:
                    # Check to see if event exists
                    if request.method == 'POST':
                        current_user = User.query.filter_by(id=user_id).first()
                        print(current_user)
                        result = event.create_reservation(current_user)
                        print(result)
                        if result == "Reservation Created":
                            return jsonify({"message" : "RSVP Successful"}), 201
                        return jsonify({"message" : "Reservation already created!"}), 302

                    guests = event.rsvp.all()
                    created_by = event.created_by
                    print(created_by)
                    if user_id == created_by:
                        if guests:
                            attending_visitors = []
                            for user in guests:
                                new= {
                                    "username" : user.username,
                                    "email" : user.email
                                }
                                attending_visitors.append(new)
                            return make_response(jsonify(attending_visitors)), 200

                        response = {"message" : "No visitors"}
                        return make_response(jsonify(response)), 200
                    else:
                        response = {
                            "message": "You can only see visitors of your own event!"
                        }
                        return jsonify(response), 401
                else:
                    response = {"message" : "Event does not exist!"}
                    return make_response(jsonify(response)), 404
            else:
                response = {"message" : "UNAUTHORIZED! Please login or sign up!"}
                return make_response(jsonify(response)), 401	
        else:
            response = {"message" : "Logged out. Please login again!"}
            return make_response(jsonify(response)), 401		
    else:
        response = {"message" : "UNAUTHORIZED! Please login or sign up!"}
        return make_response(jsonify(response)), 401

@events.route('/api/v2/events/all', methods=['GET'])
@events.route('/api/v2/events/all/page=<int:page>', methods=['GET'])
@events.route('/api/v2/events/all/page=<int:page>&limit=<int:limit>', methods=['GET'])
def all_events(limit=4, page=1):
    """Get all events in the system, no login required"""
    events = Events.query.paginate(page, per_page = limit, error_out=False).items
    results = []

    if events:
        for event in events:
            obj = {
                'id': event.id,
                'name' : event.name,
                'category' : event.category,
                'location' : event.location,
                'date' : event.date,
                'description' : event.description

            }
            results.append(obj)

        return make_response(jsonify(results)), 200
    else:
        results = {
            "message":"Events not found!"
        }
        return make_response(jsonify(results)), 404

@events.route('/api/v2/search', methods=['POST'])
@events.route('/api/v2/search/page=<int:page>&limit=<int:limit>', methods=['POST'])
def search(limit=2, page=1):
    """Search for events in the system"""
    # events = Events.query.paginate(page, per_page = 6, error_out=True).items
    # result = request.get_json()
    category = request.args.get("category")
    location = request.args.get("location")
    # get q search value and use if available
    q = request.args.get("q")						
    if category:
        filtered_events = Events.query.filter(Events.category.ilike('%{}%'.format(category)))\
        .paginate(page, per_page = limit, error_out=False).items
        event_list = []
        if filtered_events:
            for event in filtered_events:
                found_event = {'name': event.name, 'category': event.category, 'location': event.location,\
                'date': event.date, 'description': event.description}
                event_list.append(found_event)
            return jsonify({'Events belonging to this category': event_list}), 200

        return jsonify({'message': 'There are no events related to this category'}), 404
    elif location:
        filtered_events = Events.query.filter(Events.location.ilike('%{}%'.format(location)))\
        .paginate(page, per_page = limit, error_out=False).items
        event_list = []
        if filtered_events:
            for event in filtered_events:
                found_event = {'name': event.name, 'category': event.category, 'location': event.location,\
                'date': event.date, 'description': event.description}
                event_list.append(found_event)
            return jsonify({'Existing Events in this location': event_list}), 200

        return jsonify({'message': 'There are no existing events in this location'}), 404
    elif q:
        filtered_events = Events.query.filter(Events.name.ilike('%{}%'.format(q)))\
        .paginate(page, per_page = limit, error_out=False).items
        event_list = []
        if filtered_events:
            for event in filtered_events:
                found_event = {'name': event.name, 'category': event.category, 'location': event.location,\
                'date': event.date, 'description': event.description}
                event_list.append(found_event)
            return jsonify({'Existing Events': event_list}), 200

        return jsonify({'message': 'No existing events'}), 404
    else:
        return jsonify({'Warning': 'Cannot comprehend the given search parameter'})