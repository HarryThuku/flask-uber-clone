# -*- coding: utf-8 -*-
"""Customer section, including customer registration and ride requesting."""
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    abort)
from flask_breadcrumbs import default_breadcrumb_root, register_breadcrumb
from flask_login import login_user, login_required, current_user, logout_user
from flask_paginate import get_page_parameter, Pagination

from flask_uber_clone.utils import flash_errors
from .forms import RiderLoginForm, RiderRegisterForm, NewOrderForm, \
    CancelOrderForm, RateOrderForm
from .models import Rider, Route, PendingOrder

blueprint = Blueprint("rider", __name__, static_folder="../static")
default_breadcrumb_root(blueprint, '.rider')


def load_user(user_id):
    """Load user by ID."""
    user_id = int(user_id)
    if user_id % 2 == 1:
        return None
    return Rider.get_by_id(user_id / 2)


@blueprint.record_once
def on_load(state):
    """
    http://stackoverflow.com/a/20172064/742173

    :param state: state
    """
    blueprint.load_user = load_user
    state.app.login_manager.blueprint_login_views[
        blueprint.name] = 'rider.login'


@blueprint.route("/", methods=["GET", "POST"])
@register_breadcrumb(blueprint, ".", "Rider")
@login_required
def home():
    if current_user.pending_order:
        delete_form = CancelOrderForm()
        return render_template("rider/order.html",
                               delete_form=delete_form)
    elif current_user.taken_order:
        return render_template("rider/taken.html")

    order_form = NewOrderForm(request.form)

    if request.method == "POST":
        if order_form.validate_on_submit():
            route = Route.create(
                x1=order_form.x1.data,
                y1=order_form.y1.data,
                x2=order_form.x2.data,
                y2=order_form.y2.data
            )

            PendingOrder.create(
                rider_id=current_user.id,
                route_id=route.id,
                people_count=order_form.ppl_cnt.data
            )

            return redirect(url_for("rider.home"))
        else:
            flash_errors(order_form)

    return render_template("rider/new_order.html", order_form=order_form)


@blueprint.route("/order/<int:order_id>/delete", methods=["POST"])
@login_required
def cancel_order(order_id):
    form = CancelOrderForm(request.form)
    if form.validate_on_submit():
        order = PendingOrder.query.get_or_404(order_id)

        if order and order.rider_id == current_user.id:
            order.delete()
            flash("Order deleted", "info")
    else:
        flash_errors(form)

    return redirect(url_for("rider.home"))


@blueprint.route("/history", methods=["GET"])
@register_breadcrumb(blueprint, ".history", "My Trips")
@login_required
def history():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 15
    offset = (page - 1) * per_page

    orders_query = current_user.finished_orders
    orders = orders_query.limit(per_page).offset(offset)

    pagination = Pagination(page=page, per_page=per_page,
                            total=orders_query.count(),
                            bs_version=4,
                            record_name='orders')

    return render_template("rider/history.html",
                           orders=orders,
                           pagination=pagination)


@blueprint.route("/finished/<int:finished_id>", methods=["GET", "POST"])
@register_breadcrumb(blueprint, ".history.finished", "",
                     dynamic_list_constructor=lambda: [
                         {'text': "Finished order", 'url': ""}])
@login_required
def finished(finished_id):
    order = current_user.finished_orders.filter_by(id=finished_id).one_or_none()
    if order is None:
        abort(404)

    form = RateOrderForm(request.form)
    if request.method == "GET":
        if order.rating:
            form.mark.data = int(order.rating)

    if request.method == "POST":
        if form.validate_on_submit():
            current_app.logger.debug(order.id)
            order.update(rating=form.mark.data)

            return redirect(url_for("rider.history"))
        else:
            flash_errors(form)

    return render_template("rider/finished.html", finished_order=order,
                           form=form)


@blueprint.route("/login/", methods=["GET", "POST"])
def login():
    """Rider login."""
    if current_user.is_authenticated:
        return redirect(url_for("rider.home"))
    form = RiderLoginForm(request.form)
    current_app.logger.info("Hello from the home page!")
    # Handle logging in
    if request.method == "POST":
        if form.validate_on_submit():
            login_user(form.user)
            flash("You are logged in.", "success")
            redirect_url = request.args.get("next") or url_for(
                "rider.home")
            return redirect(redirect_url)
        else:
            flash_errors(form)
    return render_template("public/login.html", form=form)


@blueprint.route("/register/", methods=["GET", "POST"])
def register():
    """Register new user."""
    form = RiderRegisterForm(request.form)
    if form.validate_on_submit():
        Rider.create(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
            active=True,
        )
        flash("Thank you for registering. You can now log in.", "success")
        return redirect(url_for("rider.home"))
    else:
        flash_errors(form)
    return render_template("public/register.html", form=form)


@blueprint.route("/logout/")
@login_required
def logout():
    """Logout."""
    logout_user()
    flash("You are logged out.", "info")
    return redirect(request.args.get("next") or url_for("rider.home"))
