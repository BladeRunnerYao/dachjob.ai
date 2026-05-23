FROM node:26-alpine

WORKDIR /app

COPY app/frontend/package*.json ./
RUN npm ci

COPY app/frontend/ .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
