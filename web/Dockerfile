# ponytail: single stage. Image is fat (~600MB) but builds on a 2GB VM without
# juggling standalone output. Switch to output:"standalone" + multi-stage if disk hurts.
FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
