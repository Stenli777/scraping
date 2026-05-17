class MediaError(Exception):
    """Base media pipeline error."""


class MediaDisabledError(MediaError):
    pass


class MediaProviderError(MediaError):
    pass


class MediaGenerationDisabledError(MediaError):
    pass
