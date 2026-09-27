export class Book {
  constructor({ id, name, author, description, price, countInStock, image }) {
    this.id = id;
    this.name = name;
    this.author = author;
    this.description = description;
    this.price = price;
    this.countInStock = countInStock;
    this.image = image;
  }
}
