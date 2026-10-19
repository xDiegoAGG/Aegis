FROM node:20-alpine

WORKDIR /app

COPY shared /app/shared

COPY services/catalog-service/package*.json /app/services/catalog-service/
WORKDIR /app/services/catalog-service
RUN npm install --omit=dev --legacy-peer-deps

COPY services/catalog-service/src /app/services/catalog-service/src
# Table seed, run as a Kubernetes Job (kubernetes/seed-books-job.yaml)
COPY services/catalog-service/seed /app/services/catalog-service/seed

ENV NODE_ENV=production
EXPOSE 3003 50053
CMD ["node", "src/server.js"]
