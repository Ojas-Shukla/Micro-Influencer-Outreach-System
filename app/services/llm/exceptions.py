class LLMError(RuntimeError):
    """Base error for provider and generated-message failures."""


class LLMConfigurationError(LLMError):
    """The selected provider is missing required configuration."""


class LLMProviderError(LLMError):
    """The provider request failed or returned an unusable response."""


class MessageValidationError(LLMError):
    """Generated messages failed schema, policy, or content validation."""