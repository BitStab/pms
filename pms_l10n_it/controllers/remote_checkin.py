# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging
from datetime import datetime, timedelta

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class RemoteCheckinController(http.Controller):

    @http.route('/remote-checkin/<string:token>', type='http', auth='public', website=True, csrf=False)
    def remote_checkin_form(self, token, **kwargs):
        """Display remote check-in form"""
        try:
            # Find and validate token
            token_obj = request.env['pms.remote.checkin.token'].sudo().search([
                ('name', '=', token)
            ], limit=1)
            
            if not token_obj:
                return request.render('pms_l10n_it.remote_checkin_error', {
                    'error_message': _('Invalid check-in link'),
                    'error_detail': _('The check-in link you used is not valid or has been deleted.')
                })
            
            try:
                token_obj.validate_token_access()
            except UserError as e:
                return request.render('pms_l10n_it.remote_checkin_error', {
                    'error_message': _('Check-in link expired'),
                    'error_detail': str(e)
                })
            
            # Get reservation details
            reservation = token_obj.reservation_id
            
            # Get countries for dropdown
            countries = request.env['res.country'].sudo().search([
                ('alloggiati_web_active', '=', True)
            ], order='name')
            
            # Get existing check-in data if any
            existing_data = token_obj.checkin_data_ids
            
            # Prepare context
            context = {
                'token_obj': token_obj,
                'reservation': reservation,
                'property': reservation.pms_property_id,
                'countries': countries,
                'existing_data': existing_data,
                'document_types': [
                    ('passport', _('Passport')),
                    ('id_card', _('ID Card')),
                    ('driving_license', _('Driving License')),
                    ('other', _('Other')),
                ],
                'genders': [
                    ('M', _('Male')),
                    ('F', _('Female')),
                ]
            }
            
            return request.render('pms_l10n_it.remote_checkin_form', context)
            
        except Exception as e:
            _logger.error("Error in remote check-in form: %s", str(e))
            return request.render('pms_l10n_it.remote_checkin_error', {
                'error_message': _('System Error'),
                'error_detail': _('An unexpected error occurred. Please contact the property directly.')
            })

    @http.route('/remote-checkin/<string:token>/submit', type='http', auth='public', methods=['POST'], csrf=False)
    def remote_checkin_submit(self, token, **kwargs):
        """Process remote check-in form submission"""
        try:
            # Find and validate token
            token_obj = request.env['pms.remote.checkin.token'].sudo().search([
                ('name', '=', token)
            ], limit=1)
            
            if not token_obj:
                return self._return_error(_('Invalid token'))
            
            token_obj.validate_token_access()
            
            # Parse guest data from form
            guest_data = self._parse_guest_data(kwargs)
            
            if not guest_data:
                return self._return_error(_('No guest data provided'))
            
            # Validate and save guest data
            for guest_info in guest_data:
                try:
                    self._validate_guest_data(guest_info)
                    
                    # Create or update check-in data
                    existing_data = request.env['pms.remote.checkin.data'].sudo().search([
                        ('token_id', '=', token_obj.id),
                        ('firstname', '=', guest_info['firstname']),
                        ('lastname', '=', guest_info['lastname']),
                    ])
                    
                    if existing_data:
                        existing_data.write(guest_info)
                    else:
                        guest_info['token_id'] = token_obj.id
                        request.env['pms.remote.checkin.data'].sudo().create(guest_info)
                        
                except ValidationError as e:
                    return self._return_error(str(e))
            
            # Complete check-in process
            try:
                token_obj.complete_checkin()
                
                return request.render('pms_l10n_it.remote_checkin_success', {
                    'reservation': token_obj.reservation_id,
                    'property': token_obj.property_id,
                    'guest_count': len(guest_data)
                })
                
            except Exception as e:
                _logger.error("Error completing remote check-in: %s", str(e))
                return self._return_error(_('Error completing check-in: %s') % str(e))
            
        except Exception as e:
            _logger.error("Error in remote check-in submit: %s", str(e))
            return self._return_error(_('System error occurred'))

    @http.route('/remote-checkin/<string:token>/states', type='json', auth='public')
    def get_states_for_country(self, token, country_id):
        """Get states for a country (AJAX endpoint)"""
        try:
            if not country_id:
                return []
            
            states = request.env['res.country.state'].sudo().search([
                ('country_id', '=', int(country_id))
            ], order='name')
            
            return [{'id': state.id, 'name': state.name} for state in states]
            
        except Exception as e:
            _logger.error("Error getting states for country: %s", str(e))
            return []

    @http.route('/remote-checkin/<string:token>/cities', type='json', auth='public')
    def get_cities_for_state(self, token, state_id):
        """Get cities for a state (AJAX endpoint)"""
        try:
            if not state_id:
                return []
            
            cities = request.env['res.city'].sudo().search([
                ('state_id', '=', int(state_id))
            ], order='name', limit=100)  # Limit to prevent performance issues
            
            return [{'id': city.id, 'name': city.name} for city in cities]
            
        except Exception as e:
            _logger.error("Error getting cities for state: %s", str(e))
            return []

    def _parse_guest_data(self, form_data):
        """Parse guest data from form submission"""
        guest_data = []
        
        # Form data should be in format: guest_0_firstname, guest_0_lastname, etc.
        guest_indices = set()
        for key in form_data.keys():
            if key.startswith('guest_') and '_' in key:
                try:
                    index = int(key.split('_')[1])
                    guest_indices.add(index)
                except (ValueError, IndexError):
                    continue
        
        for index in guest_indices:
            guest_info = self._extract_guest_info(form_data, index)
            if guest_info:
                guest_data.append(guest_info)
        
        return guest_data

    def _extract_guest_info(self, form_data, index):
        """Extract guest information for a specific index"""
        prefix = f'guest_{index}_'
        
        # Required fields
        firstname = form_data.get(f'{prefix}firstname', '').strip()
        lastname = form_data.get(f'{prefix}lastname', '').strip()
        
        if not firstname or not lastname:
            return None
        
        guest_info = {
            'firstname': firstname,
            'lastname': lastname,
            'birthdate_date': form_data.get(f'{prefix}birthdate_date'),
            'gender': form_data.get(f'{prefix}gender'),
            'nationality_id': int(form_data.get(f'{prefix}nationality_id', 0)) or None,
            'residence_country_id': int(form_data.get(f'{prefix}residence_country_id', 0)) or None,
            'residence_state_id': int(form_data.get(f'{prefix}residence_state_id', 0)) or None,
            'residence_city_id': int(form_data.get(f'{prefix}residence_city_id', 0)) or None,
            'document_type': form_data.get(f'{prefix}document_type'),
            'document_number': form_data.get(f'{prefix}document_number', '').strip(),
            'document_expedition_date': form_data.get(f'{prefix}document_expedition_date'),
            'document_expiry_date': form_data.get(f'{prefix}document_expiry_date'),
            'email': form_data.get(f'{prefix}email', '').strip(),
            'phone': form_data.get(f'{prefix}phone', '').strip(),
            'privacy_consent': form_data.get(f'{prefix}privacy_consent') == 'on',
            'marketing_consent': form_data.get(f'{prefix}marketing_consent') == 'on',
        }
        
        # Convert date strings to date objects
        for date_field in ['birthdate_date', 'document_expedition_date', 'document_expiry_date']:
            if guest_info[date_field]:
                try:
                    guest_info[date_field] = datetime.strptime(guest_info[date_field], '%Y-%m-%d').date()
                except ValueError:
                    guest_info[date_field] = None
        
        return guest_info

    def _validate_guest_data(self, guest_info):
        """Validate guest data"""
        errors = []
        
        # Required fields
        if not guest_info.get('firstname'):
            errors.append(_('First name is required'))
        if not guest_info.get('lastname'):
            errors.append(_('Last name is required'))
        if not guest_info.get('birthdate_date'):
            errors.append(_('Birth date is required'))
        if not guest_info.get('gender'):
            errors.append(_('Gender is required'))
        if not guest_info.get('nationality_id'):
            errors.append(_('Nationality is required'))
        if not guest_info.get('residence_country_id'):
            errors.append(_('Country of residence is required'))
        if not guest_info.get('document_type'):
            errors.append(_('Document type is required'))
        if not guest_info.get('document_number'):
            errors.append(_('Document number is required'))
        if not guest_info.get('document_expedition_date'):
            errors.append(_('Document issue date is required'))
        if not guest_info.get('privacy_consent'):
            errors.append(_('Privacy consent is required'))
        
        # Date validations
        if guest_info.get('birthdate_date'):
            if guest_info['birthdate_date'] > datetime.now().date():
                errors.append(_('Birth date cannot be in the future'))
        
        if guest_info.get('document_expedition_date'):
            if guest_info['document_expedition_date'] > datetime.now().date():
                errors.append(_('Document issue date cannot be in the future'))
        
        if (guest_info.get('document_expedition_date') and guest_info.get('document_expiry_date') and
            guest_info['document_expiry_date'] <= guest_info['document_expedition_date']):
            errors.append(_('Document expiry date must be after issue date'))
        
        # Age validation for document requirement
        if guest_info.get('birthdate_date'):
            age = (datetime.now().date() - guest_info['birthdate_date']).days / 365.25
            if age < 14:
                # Minors under 14 might not need all document details
                pass
        
        if errors:
            raise ValidationError('\n'.join(errors))

    def _return_error(self, error_message):
        """Return error page"""
        return request.render('pms_l10n_it.remote_checkin_error', {
            'error_message': _('Check-in Error'),
            'error_detail': error_message
        })

    @http.route('/remote-checkin/<string:token>/status', type='json', auth='public')
    def get_checkin_status(self, token):
        """Get current status of remote check-in (AJAX endpoint)"""
        try:
            token_obj = request.env['pms.remote.checkin.token'].sudo().search([
                ('name', '=', token)
            ], limit=1)
            
            if not token_obj:
                return {'error': 'Invalid token'}
            
            return {
                'state': token_obj.state,
                'expires_at': token_obj.expires_at.isoformat() if token_obj.expires_at else None,
                'guest_count': len(token_obj.checkin_data_ids),
                'completed_date': token_obj.completed_date.isoformat() if token_obj.completed_date else None,
            }
            
        except Exception as e:
            _logger.error("Error getting check-in status: %s", str(e))
            return {'error': 'System error'}