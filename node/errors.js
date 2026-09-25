export class ImageGenError extends Error {
  constructor(message, exitCode = 1) {
    super(message);
    this.name = new.target.name;
    this.exitCode = exitCode;
  }
}

export class ConfigError extends ImageGenError {
  constructor(message) {
    super(message, 2);
  }
}

export class RequestError extends ImageGenError {
  constructor(message) {
    super(message, 2);
  }
}

export class ProviderError extends ImageGenError {}

export class OutputError extends ImageGenError {}
