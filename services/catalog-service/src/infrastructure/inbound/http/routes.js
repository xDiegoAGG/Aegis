import { Router } from "express";

export const makeBooksRouter = (controller) => {
  const router = Router();
  router.get("/", controller.list);
  router.get("/:id", controller.detail);
  return router;
};
