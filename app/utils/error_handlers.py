"""Global error handlers for the API."""
import logging
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Registra handlers de erro globais para a aplicação."""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Requisição inválida."""
        return jsonify({
            "error": {
                "code": "bad_request",
                "message": "Requisição inválida. Verifique os parâmetros enviados.",
                "details": getattr(error, "description", str(error))
            }
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Não autorizado."""
        return jsonify({
            "error": {
                "code": "unauthorized",
                "message": "Autenticação necessária. Força credenciais válidas."
            }
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """Proibido."""
        return jsonify({
            "error": {
                "code": "forbidden",
                "message": "Você não tem permissão para acessar este recurso."
            }
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Recurso não encontrado."""
        return jsonify({
            "error": {
                "code": "not_found",
                "message": f"Recurso não encontrado: {request.path}"
            }
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Método não permitido."""
        return jsonify({
            "error": {
                "code": "method_not_allowed",
                "message": f"Método {request.method} não permitido para {request.path}"
            }
        }), 405
    
    @app.errorhandler(409)
    def conflict(error):
        """Conflito."""
        return jsonify({
            "error": {
                "code": "conflict",
                "message": getattr(error, "description", "Conflito com o estado atual do recurso.")
            }
        }), 409
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        """Entidade não processável."""
        return jsonify({
            "error": {
                "code": "unprocessable_entity",
                "message": "Entidade não processável. Verifique os dados enviados."
            }
        }), 422
    
    @app.errorhandler(429)
    def too_many_requests(error):
        """Muitas requisições."""
        return jsonify({
            "error": {
                "code": "too_many_requests",
                "message": "Muitas requisições. Aguarde antes de tentar novamente."
            }
        }), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Erro interno do servidor."""
        logger.error(f"Internal server error: {error}", exc_info=True)
        return jsonify({
            "error": {
                "code": "internal_server_error",
                "message": "Erro interno do servidor. Tente novamente em instantes."
            }
        }), 500
    
    @app.errorhandler(502)
    def bad_gateway(error):
        """Gateway inválido."""
        return jsonify({
            "error": {
                "code": "bad_gateway",
                "message": "Serviço externo indisponível. Tente novamente em instantes."
            }
        }), 502
    
    @app.errorhandler(503)
    def service_unavailable(error):
        """Serviço indisponível."""
        return jsonify({
            "error": {
                "code": "service_unavailable",
                "message": "Serviço temporariamente indisponível. Tente novamente em instantes."
            }
        }), 503
    
    # Handler genérico para exceções não tratadas
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handler genérico para exceções não tratadas."""
        if isinstance(error, HTTPException):
            return jsonify({
                "error": {
                    "code": error.code or 500,
                    "message": error.description or str(error)
                }
            }), error.code or 500
        
        # Log do erro completo
        logger.error(f"Unhandled exception: {error}", exc_info=True)
        
        return jsonify({
            "error": {
                "code": "internal_server_error",
                "message": "Erro interno inesperado. Entre em contato com o suporte."
            }
        }), 500
