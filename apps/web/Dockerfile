FROM node:26-alpine

WORKDIR /app

COPY apps/web/package*.json ./
RUN npm ci

COPY apps/web/ .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
