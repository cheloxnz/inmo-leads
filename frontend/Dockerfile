FROM node:18-alpine AS build

WORKDIR /app

COPY package.json yarn.lock* ./
RUN yarn install --frozen-lockfile 2>/dev/null || yarn install

COPY . .

ARG REACT_APP_BACKEND_URL
ARG REACT_APP_LANDING_MODE=inmobiliaria
ARG REACT_APP_BUSINESS_NAME
ARG REACT_APP_BUSINESS_TAGLINE
ARG REACT_APP_WHATSAPP_NUMBER

RUN yarn build

FROM node:18-alpine

WORKDIR /app

RUN yarn global add serve

COPY --from=build /app/build ./build

EXPOSE 3000

CMD ["serve", "-s", "build", "-l", "3000"]
