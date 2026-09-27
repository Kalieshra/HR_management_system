FROM node:22-alpine

WORKDIR /app

# Install dependencies first so the layer caches across source edits.
# These are musl builds (next-swc, @parcel/watcher) and must not be replaced by
# the host's glibc ones — hence the `/app/node_modules` volume in compose.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# node:alpine ships a `node` user at uid/gid 1000, which matches a typical Linux
# desktop account. Running as it means the bind-mounted working tree and the
# node_modules volume stay writable, and nothing the container creates lands in
# your checkout owned by root.
RUN chown -R node:node /app
USER node

EXPOSE 3000
CMD ["npm", "run", "dev"]
