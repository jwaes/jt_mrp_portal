import base64
from collections import OrderedDict
from datetime import datetime

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, Response
from odoo.tools import image_process
from odoo.tools.translate import _
from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager, get_records_pager


class CustomerPortal(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        partner = request.env.user.partner_id

        MrpProduction = request.env['mrp.production']

        if 'production_count'  in counters:
            values['production_count'] = MrpProduction.sudo().search_count(self._prepare_mrpproduction_domain(partner)) \
                if MrpProduction.check_access_rights('read', raise_exception=False) else 0

        return values  

    def _prepare_mrpproduction_domain(self, partner):

        parent_location = http.request.env.ref('stock.stock_location_locations', raise_if_not_found=False)

        return [
            ('location_src_id.location_id', '!=', parent_location.id),
            ('location_src_id','in', partner.commercial_partner_id.property_stock_subcontractor.ids),
            ('state','not in',('cancel','done'))
        ]

    def _get_mrpproduction_searchbar_sortings(self):
        return {
            'date': {'label': _('Due Date'), 'production': 'date_planned_finished desc'},
            # 'name': {'label': _('Reference'), 'order': 'name'},
            'product': {'label': _('Product'), 'production': 'product_id'},
            # 'state': {'label': _('State'), 'production': 'state'},
        }


    def _mrpproduction_get_page_view_values(self, production, access_token, **kwargs):
        #
        def resize_to_48(b64source):
            if not b64source:
                b64source = base64.b64encode(request.env['ir.http']._placeholder())
            return image_process(b64source, size=(48, 48))

        values = {
            'production': production,
            'resize_to_48': resize_to_48,
            'report_type': 'html',
            'commercial_partner': request.env.user.partner_id.commercial_partner_id,
        }

        history = 'my_productions_history'
        return self._get_page_view_values(production, access_token, values, history, False, **kwargs)   

    @http.route(['/my/productions', '/my/productions/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_productions(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):        
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        MrpProduction = request.env['mrp.production'] 

        domain = self._prepare_mrpproduction_domain(partner)

        searchbar_sortings = self._get_mrpproduction_searchbar_sortings()

        searchbar_filters =  {
                'all': {'label': _('All'), 'domain': [('components_availability_state', 'in', ['available', 'expected', 'late'])]},
                'available': {'label': _('Available'), 'domain': [('components_availability_state', 'in', ['available'])]},
                'expected': {'label': _('Expected'), 'domain': [('components_availability_state', '=', 'cancel')]},
                'late': {'label': _('Late'), 'domain': [('components_availability_state', '=', 'late')]},
            }        

        # default sortby order
        if not sortby:
            sortby = 'date'
        sort_order = searchbar_sortings[sortby]['production']    

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]        

        if searchbar_filters:
            # default filter
            if not filterby:
                filterby = 'all'
            domain += searchbar_filters[filterby]['domain']  

        # count for pager
        production_count = MrpProduction.sudo().search_count(domain)   

        # make pager
        pager = portal_pager(
            url="/my/productions",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=production_count,
            page=page,
            step=self._items_per_page
        )       

        # search the count to display, according to the pager data
        productions = MrpProduction.sudo().search(domain, order=sort_order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_productions_history'] = productions.ids[:100]      

        values.update({
            'date': date_begin,
            'productions': productions.sudo(),
            'page_name': 'productions',
            'pager': pager,
            'default_url': '/my/productions',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
            'sortby': sortby,
        })
        return request.render("jt_mrp_portal.portal_my_productions", values)                                  


    @http.route(['/my/productions/<int:production_id>'], type='http', auth="public", website=True)
    def portal_production_page(self, production_id, report_type=None, access_token=None, message=False, download=False, **kw):        
        try:
            production_id = self._document_check_access('mrp.production', production_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # report_type = kw.get('report_type')
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=production_id, report_type=report_type, report_ref='mrp.action_report_production_order', download=download)            

        values = self._mrpproduction_get_page_view_values(production_id, access_token, **kw)

        history = request.session.get('my_productions_history', [])
        values.update(get_records_pager(history, production_id))     




        return request.render("jt_mrp_portal.portal_my_production", values)        