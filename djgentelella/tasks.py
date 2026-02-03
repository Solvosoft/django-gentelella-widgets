import logging

from djgentelella.chunked_upload.utils import delete_expired_uploads

logger = logging.getLogger('djgentelella')


def delete_expired_chunked_uploads():
    """
    Delete expired chunked uploads.

    This function is intended to be called by scheduled tasks (e.g., Celery).
    It does not support interactive mode since scheduled tasks run unattended.

    Returns:
        dict: A dictionary with 'status' and deletion counts or error message.
    """
    try:
        logger.info('Starting deletion of expired chunked uploads')

        result = delete_expired_uploads()

        logger.info(
            f"Deletion completed: {result['complete']} complete, "
            f"{result['uploading']} incomplete uploads deleted"
        )

        return {
            'status': 'success',
            'complete': result['complete'],
            'uploading': result['uploading'],
        }

    except Exception as e:
        logger.error(f'Error deleting chunked uploads: {str(e)}', exc_info=True)
        return {
            'status': 'error',
            'message': str(e)
        }
