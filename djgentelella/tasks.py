import logging

from django.core.management import call_command
logger = logging.getLogger('djgentelella')

def delete_documents_chunked_uploads(interactive=False):
    """
    Elimina chunked uploads expirados llamando al comando de djgentelella

    Args:
        interactive: Si es True, pedirá confirmación antes de cada eliminación
                     (solo útil en ejecución manual, no en tareas programadas)
    """
    try:
        logger.info('Iniciando eliminación de chunked uploads expirados')

        # Llamar al comando delete_expired_uploads de djgentelella
        call_command('delete_expired_uploads', interactive=interactive)

        logger.info('Eliminación de chunked uploads completada exitosamente')

        return {
            'status': 'success',
            'message': 'Expired chunked uploads deleted successfully'
        }

    except Exception as e:
        logger.error(f'Error eliminando chunked uploads: {str(e)}', exc_info=True)
        return {
            'status': 'error',
            'message': str(e)
        }
