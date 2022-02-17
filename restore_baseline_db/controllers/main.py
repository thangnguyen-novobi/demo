import jinja2
import json
import os
from werkzeug.datastructures import FileStorage

import odoo
import odoo.modules.registry
from odoo import http, tools
from odoo.service import db, security
from odoo.addons.web.controllers.main import DBNAME_PATTERN, db_monodb, Database as DB
from odoo.http import content_disposition, dispatch_rpc, request, Response

loader = jinja2.PackageLoader('odoo.addons.restore_baseline_db', "views")
env = jinja2.Environment(loader=loader, autoescape=True)
env.filters["json"] = json.dumps


class Database(DB):

    def _render_template(self, **d):
        d.setdefault('manage',True)
        d['insecure'] = odoo.tools.config.verify_admin_password('admin')
        d['list_db'] = odoo.tools.config['list_db']
        d['langs'] = odoo.service.db.exp_list_lang()
        d['countries'] = odoo.service.db.exp_list_countries()
        d['pattern'] = DBNAME_PATTERN
        # databases list
        d['databases'] = []
        try:
            d['databases'] = http.db_list()
            d['incompatible_databases'] = odoo.service.db.list_db_incompatible(d['databases'])
        except odoo.exceptions.AccessDenied:
            monodb = db_monodb()
            if monodb:
                d['databases'] = [monodb]
        return env.get_template("database_manager.html").render(d)

    @http.route('/web/database/baseline', type='http', auth="none", methods=['POST'], csrf=False)
    def baseline(self, master_pwd):
        insecure = odoo.tools.config.verify_admin_password('admin')
        if insecure and master_pwd:
            dispatch_rpc('db', 'change_admin_password', ["admin", master_pwd])
        try:
            db.check_super(master_pwd)

            path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'static', 'baseline_db', 'baseline_db.zip')

            file = None
            with open(path, 'rb') as fp:
                file = FileStorage(fp)
                if "odoosandbox" in http.db_list():
                    self.drop(master_pwd=master_pwd, name="odoosandbox")
                    self.restore(master_pwd=master_pwd, backup_file=file, name="odoosandbox", copy=True)
                else:
                    raise Exception("Couldn't find database named odoosandbox")

            return http.local_redirect('/web/database/manager')
        except Exception as e:
            error = "Database baseline rollback error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)
