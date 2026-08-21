"""Configuration module for Speechly application."""
import os


# Map environment names to configuration classes
CONFIG_MAP = {
    'development': 'app.config.development.DevelopmentConfig',
    'production': 'app.config.production.ProductionConfig',
    'testing': 'app.config.testing.TestingConfig',
}


def get_config(env=None):
    """
    Get configuration class based on environment.

    Args:
        env: Environment name ('development', 'production', 'testing')
             If None, reads from FLASK_ENV environment variable

    Returns:
        Configuration class instance
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')

    config_path = CONFIG_MAP.get(env)
    if not config_path:
        raise ValueError(f"Unknown environment: {env}. Valid options: {list(CONFIG_MAP.keys())}")

    # Import the configuration class
    module_path, class_name = config_path.rsplit('.', 1)
    module = __import__(module_path, fromlist=[class_name])
    config_class = getattr(module, class_name)

    return config_class()


__all__ = ['get_config', 'CONFIG_MAP']
