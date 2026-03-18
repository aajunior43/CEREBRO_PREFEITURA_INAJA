from flask import Flask


def register_all_blueprints(app: Flask):
    from blueprints.core import bp as core_bp
    from blueprints.credores import bp as credores_bp
    from blueprints.rpas import bp as rpas_bp
    from blueprints.kanban import bp as kanban_bp
    from blueprints.documentos import bp as documentos_bp
    from blueprints.autentique import bp as autentique_bp
    from blueprints.cnpj import bp as cnpj_bp
    from blueprints.pdf_tools import bp as pdf_tools_bp
    from blueprints.ia import bp as ia_bp
    from blueprints.despesas import bp as despesas_bp
    from blueprints.prazos import bp as prazos_bp
    from blueprints.protocolos import bp as protocolos_bp
    from blueprints.fornecimento import bp as fornecimento_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(credores_bp, url_prefix='/api')
    app.register_blueprint(rpas_bp, url_prefix='/api')
    app.register_blueprint(kanban_bp, url_prefix='/api')
    app.register_blueprint(documentos_bp, url_prefix='/api')
    app.register_blueprint(autentique_bp, url_prefix='/api')
    app.register_blueprint(cnpj_bp, url_prefix='/api')
    app.register_blueprint(pdf_tools_bp, url_prefix='/api')
    app.register_blueprint(ia_bp, url_prefix='/api')
    app.register_blueprint(despesas_bp, url_prefix='/api')
    app.register_blueprint(prazos_bp, url_prefix='/api')
    app.register_blueprint(protocolos_bp, url_prefix='/api')
    app.register_blueprint(fornecimento_bp, url_prefix='/api')
