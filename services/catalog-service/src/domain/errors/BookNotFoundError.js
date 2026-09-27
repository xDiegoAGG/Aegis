export class BookNotFoundError extends Error {
  constructor(id) {
    super(`Book ${id} not found`);
    this.name = "BookNotFoundError";
  }
}
