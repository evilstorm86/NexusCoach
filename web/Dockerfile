# ponytail: single stage. Image is fat (~600MB) but builds on a 2GB VM without
# juggling standalone output. Switch to output:"standalone" + multi-stage if disk hurts.
FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_* is inlined at build time, so this has to be a build arg — setting it as a
# runtime env var in compose would silently leave the old value in the bundle.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

USER node
EXPOSE 3000
CMD ["npm", "start"]
