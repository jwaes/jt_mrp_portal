from odoo import api, fields, models

class MrpProduction(models.Model):
    _name = 'mrp.production'
    _inherit = ['mrp.production', 'portal.mixin']

    def _compute_access_url(self):
        super(MrpProduction, self)._compute_access_url()
        for production in self:
            production.access_url = '/my/productions/%s' % (production.id)    

    def _get_report_base_filename(self):
        self.ensure_one()
        return f'{self.name}'