from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Optional
from models import db, User, ReportTemplate, ActivityLog
import json
import logging
from datetime import datetime

templates_bp = Blueprint('templates', __name__, url_prefix='/templates')

class TemplateForm(FlaskForm):
    name = StringField('Template Name', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    content = TextAreaField('Content', validators=[DataRequired()])
    format = SelectField('Format', choices=[
        ('html', 'HTML'),
        ('text', 'Plain Text'),
        ('markdown', 'Markdown')
    ])

def log_template_activity(action, details=None):
    """Log template activity for auditing purposes"""
    try:
        activity = ActivityLog(
            user_id=current_user.id,
            action=action,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logging.error(f"Error logging template activity: {e}")
        db.session.rollback()

@templates_bp.route('/')
@login_required
def list_templates():
    # Get templates created by the current user
    own_templates = ReportTemplate.query.filter_by(user_id=current_user.id).all()
    
    # Empty list for shared templates since sharing is disabled
    shared_templates = []
    
    return render_template('templates/list.html', 
                           own_templates=own_templates, 
                           shared_templates=shared_templates)

@templates_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_template():
    form = TemplateForm()
    
    if form.validate_on_submit():
        template = ReportTemplate(
            user_id=current_user.id,
            name=form.name.data,
            description=form.description.data,
            content=form.content.data,
            format=form.format.data,
            is_shared=False  # Disable sharing
        )
        
        db.session.add(template)
        db.session.commit()
        
        log_template_activity('create_template', f"Created template: {template.name}")
        
        flash('Template created successfully!', 'success')
        return redirect(url_for('templates.list_templates'))
    
    return render_template('templates/create.html', form=form)

@templates_bp.route('/edit/<template_id>', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    template = ReportTemplate.query.get_or_404(template_id)
    
    # Only the creator can edit
    if template.user_id != current_user.id:
        flash('You cannot edit templates created by other users', 'danger')
        return redirect(url_for('templates.list_templates'))
    
    form = TemplateForm(obj=template)
    
    if form.validate_on_submit():
        template.name = form.name.data
        template.description = form.description.data
        template.content = form.content.data
        template.format = form.format.data
        template.is_shared = False  # Disable sharing
        template.shared_with = None  # Clear any existing shares
        template.updated_at = datetime.now()
        
        db.session.commit()
        
        log_template_activity('edit_template', f"Edited template: {template.name}")
        
        flash('Template updated successfully!', 'success')
        return redirect(url_for('templates.list_templates'))
    
    return render_template('templates/edit.html', form=form, template=template)

@templates_bp.route('/view/<template_id>')
@login_required
def view_template(template_id):
    template = ReportTemplate.query.get_or_404(template_id)
    
    # Check if the user has access (creator or shared with)
    if template.user_id != current_user.id and not template.is_shared_with(current_user.id):
        flash('You do not have access to this template', 'danger')
        return redirect(url_for('templates.list_templates'))
    
    # Get User query for displaying shared user names
    user_query = User.query
    
    return render_template('templates/view.html', template=template, user_query=user_query)

@templates_bp.route('/delete/<template_id>', methods=['POST'])
@login_required
def delete_template(template_id):
    template = ReportTemplate.query.get_or_404(template_id)
    
    # Only the creator can delete
    if template.user_id != current_user.id:
        flash('You cannot delete templates created by other users', 'danger')
        return redirect(url_for('templates.list_templates'))
    
    template_name = template.name
    db.session.delete(template)
    db.session.commit()
    
    log_template_activity('delete_template', f"Deleted template: {template_name}")
    
    flash('Template deleted successfully!', 'success')
    return redirect(url_for('templates.list_templates'))

@templates_bp.route('/use/<template_id>')
@login_required
def use_template(template_id):
    template = ReportTemplate.query.get_or_404(template_id)
    
    # Check if the user has access (creator or shared with)
    if template.user_id != current_user.id and not template.is_shared_with(current_user.id):
        flash('You do not have access to this template', 'danger')
        return redirect(url_for('templates.list_templates'))
    
    # Log the usage
    log_template_activity('use_template', f"Used template: {template.name}")
    
    # For HTML templates, render them directly
    if template.format == 'html':
        return render_template('templates/use_html.html', template=template)
    
    # For text templates, download them
    elif template.format == 'text':
        return render_template('templates/use_text.html', template=template)
    
    # For other formats like markdown, handle appropriately
    return render_template('templates/use.html', template=template)

@templates_bp.route('/api/templates')
@login_required
def api_list_templates():
    # Get templates for API consumption (used by JavaScript)
    own_templates = ReportTemplate.query.filter_by(user_id=current_user.id).all()
    
    templates_list = [{
        'id': template.id,
        'name': template.name,
        'description': template.description,
        'format': template.format,
        'created_at': template.created_at.strftime('%Y-%m-%d %H:%M'),
        'is_shared': template.is_shared,
        'is_own': True
    } for template in own_templates]
    
    # Get templates shared with the current user
    all_shared = ReportTemplate.query.filter_by(is_shared=True).all()
    for template in all_shared:
        if template.user_id != current_user.id and template.is_shared_with(current_user.id):
            templates_list.append({
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'format': template.format,
                'created_at': template.created_at.strftime('%Y-%m-%d %H:%M'),
                'is_shared': True,
                'is_own': False,
                'creator': template.creator.name
            })
    
    return jsonify(templates_list)