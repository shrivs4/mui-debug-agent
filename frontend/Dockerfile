#--Install Dependencies--#
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci

#--Build the app -- #

FROM node:20-alpine AS builder

WORKDIR /app    

COPY --from=deps /app/node_modules ./node_modules

COPY . .

RUN npm run build

#---Running the app---#

FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/.next/standalone ./

COPY --from=builder /app/.next/static ./.next/static

COPY --from=builder /app/public ./public

ENV HOSTNAME=0.0.0.0

CMD ["node","server.js"]