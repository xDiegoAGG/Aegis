FROM node:20-alpine

WORKDIR /app

COPY shared /app/shared

COPY services/catalog-service/package*.json /app/services/catalog-service/
WORKDIR /app/services/catalog-service
RUN npm install --omit=dev --legacy-peer-deps

COPY services/catalog-service/src /app/services/catalog-service/src

ENV NODE_ENV=production
EXPOSE 3003 50053
CMD ["node", "src/server.js"]
