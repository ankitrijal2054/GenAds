# S3 Public Access Setup for Veo 3.1 Reference Images

**Purpose:** Configure S3 bucket to allow public access to product and logo images for Veo 3.1 reference image integration.

---

## 🔧 S3 Bucket Configuration

To allow Veo 3.1 to access S3 URLs without credentials, you need to:

### 1. Disable "Block Public Access" Settings

1. Go to AWS S3 Console
2. Select your bucket (e.g., `genads-gauntlet`)
3. Go to **Permissions** tab
4. Click **Edit** under "Block public access (bucket settings)"
5. **Uncheck** all four options:
   - Block all public access
   - Block public access to buckets and objects granted through new access control lists (ACLs)
   - Block public access to buckets and objects granted through any access control lists (ACLs)
   - Block public access to buckets and objects granted through new public bucket or access point policies
   - Block public and cross-account access to buckets and objects through any public bucket or access point policies
6. Click **Save changes**
7. Type "confirm" to confirm

### 2. Add Bucket Policy for Public Read Access

Add this bucket policy (replace `YOUR_BUCKET_NAME`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
    }
  ]
}
```

**Steps:**
1. Go to **Permissions** tab
2. Click **Edit** under "Bucket policy"
3. Paste the policy above (replace `YOUR_BUCKET_NAME` with your actual bucket name)
4. Click **Save changes**

### 3. Configure CORS (Optional but Recommended)

If you're accessing from frontend, add CORS configuration:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

**Steps:**
1. Go to **Permissions** tab
2. Scroll to "Cross-origin resource sharing (CORS)"
3. Click **Edit**
4. Paste the CORS configuration above
5. Click **Save changes**

---

## ✅ Verification

After configuration:

1. Upload a test file to S3
2. Make it public-read (`ACL="public-read"`)
3. Try accessing the URL: `https://YOUR_BUCKET_NAME.s3.REGION.amazonaws.com/path/to/file.png`
4. Should load in browser without authentication

---

## 📝 Current Implementation

The code now:
- ✅ Uploads extracted product images with `ACL="public-read"`
- ✅ Returns public S3 URLs instead of local paths
- ✅ Validates URLs before passing to Veo 3.1

**Files Updated:**
- `backend/app/services/product_extractor.py` - Uploads to S3 with public-read ACL
- `backend/app/services/video_generator.py` - Validates URLs before sending to Veo 3.1

---

## 🔒 Security Note

Making S3 buckets public allows anyone with the URL to access files. Consider:
- Using presigned URLs with expiration (alternative approach)
- Restricting bucket policy to specific paths (e.g., only `/draft/product/` and `/brands/` folders)
- Using CloudFront with signed URLs (more advanced)

For now, public access is required for Veo 3.1 to access reference images.

---

**Status:** Code updated, bucket configuration pending

