
class GetApolloConfigurationFailure(Exception):
    def __init__(self, *args):
        self.args = args

    def __str__(self):
        return "Call Apollo Config Server Failure!"
