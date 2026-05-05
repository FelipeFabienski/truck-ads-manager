import warnings

def pytest_configure(config):
    # Field named 'copy' is an intentional advertising term; suppress the Pydantic shadow warning
    warnings.filterwarnings("ignore", message="Field name.*shadows an attribute in parent")
