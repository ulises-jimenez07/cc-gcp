// Cloud Run Function (2nd gen) triggered by Pub/Sub topic: image-upload
// Reads the original image from GCS, generates a 200x200 thumbnail,
// and saves it back to GCS under the "thumbnails/" prefix.

const { Storage } = require('@google-cloud/storage');
const sharp = require('sharp');

const storage = new Storage();

/**
 * Pub/Sub message format (base64-encoded JSON):
 * {
 *   "imageId": 42,
 *   "bucketName": "my-app-images",
 *   "filename": "1712345678-photo.jpg",
 *   "mimetype": "image/jpeg"
 * }
 */
exports.generateThumbnail = async (cloudEvent) => {
  // Decode the Pub/Sub message
  const rawMessage = cloudEvent.data?.message?.data;
  if (!rawMessage) {
    console.error('No message data received');
    return;
  }

  const payload = JSON.parse(Buffer.from(rawMessage, 'base64').toString('utf-8'));
  const { imageId, bucketName, filename, mimetype } = payload;

  console.log(`Processing imageId=${imageId}, file=${filename}`);

  const bucket = storage.bucket(bucketName);
  const sourceFile = bucket.file(filename);
  const thumbnailFilename = `thumbnails/thumb-${filename}`;
  const destFile = bucket.file(thumbnailFilename);

  // Download the original image into memory
  const [imageBuffer] = await sourceFile.download();

  // Generate 200x200 thumbnail using sharp (maintains aspect ratio, covers the box)
  const thumbnailBuffer = await sharp(imageBuffer)
    .resize(200, 200, { fit: 'cover' })
    .toBuffer();

  // Upload thumbnail back to GCS
  await destFile.save(thumbnailBuffer, {
    metadata: { contentType: mimetype },
    resumable: false
  });

  const thumbnailUrl = `https://storage.googleapis.com/${bucketName}/${thumbnailFilename}`;
  console.log(`Thumbnail created: ${thumbnailUrl}`);
};
