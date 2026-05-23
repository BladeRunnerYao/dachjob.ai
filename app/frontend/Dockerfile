FROM node:26-alpine

WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY app/frontend/package*.json ./
RUN npm ci

COPY app/frontend/ .
RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0"]
