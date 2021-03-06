# ----------------------------------------------------------------------------#
# Imports
# ----------------------------------------------------------------------------#

import logging
import sys
from datetime import datetime
from logging import Formatter, FileHandler

import dateutil.parser
from babel import dates
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_migrate import Migrate
from flask_moment import Moment
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from models import setup_db, Venue, Artist, Show

# ----------------------------------------------------------------------------#
# App Config.
# ----------------------------------------------------------------------------#

# to make sure it uses .env file when running it with python app.py
load_dotenv()

app = Flask(__name__)
moment = Moment(app)
app.config.from_object('config')
db = setup_db(app)
migrate = Migrate(app, db)


# ----------------------------------------------------------------------------#
# Filters.
# ----------------------------------------------------------------------------#

def format_datetime(value, format_name='medium'):
    date = value
    if type(value) is not datetime:
        date = dateutil.parser.parse(value)
    datetime_format = "EE MM, dd, y h:mma"
    if format_name == 'full':
        datetime_format = "EEEE MMMM, d, y 'at' h:mma"
    elif format_name == 'medium':
        datetime_format = "EE MM, dd, y h:mma"
    return dates.format_datetime(date, datetime_format)


app.jinja_env.filters['datetime'] = format_datetime


# ----------------------------------------------------------------------------#
# Controllers.
# ----------------------------------------------------------------------------#

@app.route('/')
def index():
    return render_template('pages/home.html')


#  Venues
#  ----------------------------------------------------------------

@app.route('/venues')
def venues():
    data = []
    areas = db.session.query(Venue.state, Venue.city).distinct()
    for state, city in areas:
        # I didn't change key name of upcoming_shows_count
        # to num_upcoming_shows as it's not used and
        # if it was used I'll change it from the front-end side
        data.append({
            "city": city,
            "state": state,
            "venues": Venue.query.filter(Venue.state == state,
                                         Venue.city == city)
        })
    return render_template('pages/venues.html', areas=data)


@app.route('/venues/search', methods=['POST'])
def search_venues():
    q = request.form.get('search_term', '')
    venues_query = Venue.query.filter(Venue.name.ilike(f'%{q}%'))

    response = {
        "count": venues_query.count(),
        "data": venues_query
    }
    return render_template('pages/search_venues.html', results=response,
                           search_term=q)


@app.route('/venues/<int:venue_id>')
def show_venue(venue_id):
    venue: Venue = Venue.query.get_or_404(venue_id)
    past_shows = db.session.query(Artist, Show).join(Show).join(Venue). \
        filter(
        Show.venue_id == venue_id,
        Show.artist_id == Artist.id,
        Show.start_time < datetime.now()
    )

    upcoming_shows = db.session.query(Artist, Show).join(Show).join(Venue). \
        filter(
        Show.venue_id == venue_id,
        Show.artist_id == Artist.id,
        Show.start_time >= datetime.now()
    )

    data = {
        "id": venue.id,
        "name": venue.name,
        "genres": venue.genres,
        "city": venue.city,
        "state": venue.state,
        "address": venue.address,
        "phone": venue.phone,
        "website": venue.website,
        "facebook_link": venue.facebook_link,
        "seeking_talent": venue.seeking_talent,
        "seeking_description": venue.seeking_description,
        "image_link": venue.image_link,
        "past_shows": [{
            'artist_id': artist.id,
            "artist_name": artist.name,
            "artist_image_link": artist.image_link,
            "start_time": show.start_time
        } for artist, show in past_shows.all()],
        "past_shows_count": past_shows.count(),
        "upcoming_shows": [{
            'artist_id': artist.id,
            "artist_name": artist.name,
            "artist_image_link": artist.image_link,
            "start_time": show.start_time
        } for artist, show in upcoming_shows.all()],
        "upcoming_shows_count": upcoming_shows.count(),
    }

    return render_template('pages/show_venue.html', venue=data)


@app.route('/venues/create', methods=['GET', 'POST'])
def create_venue():
    # it must be imported here to avoid circular import
    from forms import VenueForm
    form = VenueForm()

    if form.validate_on_submit():
        venue = Venue()
        form.populate_obj(venue)
        try:
            db.session.add(venue)
            db.session.commit()
        except SQLAlchemyError:
            print(sys.exc_info())
            db.session.rollback()
            db.session.close()
            flash(
                'An error occurred. Venue '
                + form.name.data + ' could not be listed.')
            return render_template('forms/new_venue.html', form=form)

        flash('Venue ' + venue.name + ' was successfully listed!')
        return redirect(url_for('show_venue', venue_id=venue.id))
    return render_template('forms/new_venue.html', form=form)


@app.route('/venues/<int:venue_id>/edit', methods=['POST', 'GET'])
def edit_venue(venue_id):
    # it must be imported here to avoid circular import
    from forms import VenueForm
    venue: Venue = Venue.query.get_or_404(venue_id)
    form = VenueForm(obj=venue)
    # and I'm not adding request.form as it's already added by flask-wtf
    # look here https://flask-wtf.readthedocs.io/en/stable/quickstart.html
    ###
    # Note that you don't have to pass request.form to Flask-WTF;
    # it will load automatically.
    # And the convenience validate_on_submit will check if it is a POST request
    # and if it is valid.
    ###
    venue_name = venue.name

    # this function return true only if it's a POST request and it's valid form
    # and choices are validated automatically unless validate_choices = false
    if form.validate_on_submit():
        form.populate_obj(venue)

        try:
            db.session.add(venue)
            db.session.commit()
        except SQLAlchemyError:
            print(sys.exc_info())
            db.session.rollback()
            db.session.close()
            flash(
                'An error occurred. Venue '
                + venue_name + ' could not be edited.')
            return render_template('forms/edit_venue.html', form=form,
                                   venue_name=venue_name)

        flash('Venue ' + venue.name + ' was successfully updated!')
        return redirect(url_for('show_venue', venue_id=venue_id))

    return render_template('forms/edit_venue.html', form=form,
                           venue_name=venue_name)


@app.route('/venues/<venue_id>', methods=['DELETE'])
def delete_venue(venue_id):
    v = Venue.query.get_or_404(venue_id)
    try:
        db.session.delete(v)
        db.session.commit()
    except SQLAlchemyError:
        print(sys.exc_info())
        db.session.rollback()
        flash('An error occurred. Venue ' + v.name + ' could not be deleted.')
        return '', 500
    finally:
        db.session.close()

    # BONUS CHALLENGE: Implement a button to delete a Venue
    # on a Venue Page, have it so that clicking that button
    # delete it from the db then redirect the user to the homepage
    # I'm handling it from the front end
    return '', 204


#  Artists
#  ----------------------------------------------------------------
@app.route('/artists')
def artists():
    data = db.session.query(Artist.id, Artist.name)
    return render_template('pages/artists.html', artists=data)


@app.route('/artists/search', methods=['POST'])
def search_artists():
    q = request.form.get('search_term', '')
    artists_query = Artist.query.filter(Artist.name.ilike(f'%{q}%'))

    # I didn't loop throw venues and change upcoming_shows_count
    # because it will take resources for no reason
    # so I would simply change it from the front-end size if it was used
    response = {
        "count": artists_query.count(),
        "data": artists_query
    }
    return render_template('pages/search_artists.html', results=response,
                           search_term=q)


@app.route('/artists/<int:artist_id>')
def show_artist(artist_id):
    artist: Artist = Artist.query.get_or_404(artist_id)
    past_shows = db.session.query(
        Venue, Show
    ).join(Show).join(Artist).filter(
        Show.venue_id == artist_id,
        Show.artist_id == Artist.id,
        Show.start_time < datetime.now()
    )
    upcoming_shows = db.session.query(
        Venue, Show
    ).join(Show).join(Artist).filter(
        Show.venue_id == artist_id,
        Show.artist_id == Artist.id,
        Show.start_time >= datetime.now()
    )

    data = {
        "id": artist.id,
        "name": artist.name,
        "genres": artist.genres,
        "city": artist.city,
        "state": artist.state,
        "phone": artist.phone,
        "website": artist.website,
        "facebook_link": artist.facebook_link,
        "seeking_venue": artist.seeking_venue,
        "seeking_description": artist.seeking_description,
        "image_link": artist.image_link,
        "past_shows": [{
            'artist_id': venue.id,
            "artist_name": venue.name,
            "artist_image_link": venue.image_link,
            "start_time": show.start_time
        } for venue, show in past_shows.all()],
        "past_shows_count": past_shows.count(),
        "upcoming_shows": [{
            'artist_id': venue.id,
            "artist_name": venue.name,
            "artist_image_link": venue.image_link,
            "start_time": show.start_time
        } for venue, show in upcoming_shows.all()],
        "upcoming_shows_count": upcoming_shows.count(),
    }

    return render_template('pages/show_artist.html', artist=data)


@app.route('/artists/create', methods=['GET', 'POST'])
def create_artist():
    # it must be imported here to avoid circular import
    from forms import ArtistForm
    form = ArtistForm()

    if form.validate_on_submit():
        artist = Artist()
        form.populate_obj(artist)
        try:
            db.session.add(artist)
            db.session.commit()
        except SQLAlchemyError:
            flash(
                'An error occurred. Artist '
                + form.name.data + ' could not be listed.')
            print(sys.exc_info())
            db.session.rollback()
            db.session.close()
            return render_template('forms/new_artist.html', form=form)

        flash('Artist ' + artist.name + ' was successfully listed!')
        return redirect(url_for('show_artist', artist_id=artist.id))
    return render_template('forms/new_artist.html', form=form)


@app.route('/artists/<int:artist_id>/edit', methods=['GET', 'POST'])
def edit_artist(artist_id):
    # it must be imported here to avoid circular import
    from forms import ArtistForm
    artist = Artist.query.get_or_404(artist_id)
    form = ArtistForm(obj=artist)
    artist_name = artist.name
    if form.validate_on_submit():
        form.populate_obj(artist)
        try:
            db.session.add(artist)
            db.session.commit()
        except SQLAlchemyError:
            flash(
                'An error occurred. Artist '
                + artist_name + ' could not be edited.'
            )
            print(sys.exc_info())
            db.session.rollback()
            db.session.close()
            return render_template('forms/edit_artist.html', form=form,
                                   artist_name=artist_name)
        return redirect(url_for('show_artist', artist_id=artist_id))

    return render_template('forms/edit_artist.html', form=form,
                           artist_name=artist_name)


@app.route('/artists/<artist_id>', methods=['DELETE'])
def delete_artist(artist_id):
    a = Artist.query.get_or_404(artist_id)
    try:
        db.session.delete(a)
        db.session.commit()
    except SQLAlchemyError:
        print(sys.exc_info())
        db.session.rollback()
        flash('An error occurred. Artist ' + a.name + ' could not be deleted.')
        db.session.close()
        return '', 500
    return '', 204


#  Shows
#  ----------------------------------------------------------------

@app.route('/shows')
def shows():
    data = db.session.query(Show).join(Artist).join(Venue)
    return render_template('pages/shows.html', shows=data)


@app.route('/shows/create', methods=['POST', 'GET'])
def create_show():
    from forms import ShowForm
    form = ShowForm()

    if form.validate_on_submit():
        show = Show()
        form.populate_obj(show)
        try:
            db.session.add(show)
            db.session.commit()
        except SQLAlchemyError:
            print(sys.exc_info())
            db.session.rollback()
            db.session.close()
            flash('An error occurred. Show could not be listed.')
            return render_template('forms/new_show.html', form=form)

        flash('Show was successfully listed!')
        return render_template('pages/home.html')

    return render_template('forms/new_show.html', form=form)


@app.route('/shows/search', methods=["POST"])
def search_shows():
    search_term = request.form.get('search_term', '')
    q = f"%{search_term}%"

    shows_query = db.session.query(Show).join(Artist).join(Venue).filter(or_(
        Venue.name.ilike(q),
        Artist.name.ilike(q)
    ))

    response = {
        "count": shows_query.count(),
        "data": shows_query
    }
    return render_template('pages/search_shows.html', results=response,
                           search_term=search_term)


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500


if not app.debug:
    f = '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter(f)
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

# ----------------------------------------------------------------------------#
# Launch.
# ----------------------------------------------------------------------------#

if __name__ == '__main__':
    app.run()
