import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Container, Header } from '@/components/layout'
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Select } from '@/components/ui'
import { useProjects } from '@/hooks/useProjects'
import { Upload, X } from 'lucide-react'

const moods = [
  { value: 'uplifting', label: '✨ Uplifting - Positive, energetic vibe' },
  { value: 'dramatic', label: '⚡ Dramatic - Bold, impactful' },
  { value: 'energetic', label: '🔥 Energetic - Fast-paced, dynamic' },
  { value: 'calm', label: '🌊 Calm - Serene, relaxing' },
  { value: 'luxurious', label: '👑 Luxurious - Premium, elegant' },
  { value: 'playful', label: '🎉 Playful - Fun, lighthearted' },
]

export const CreateProject = () => {
  const navigate = useNavigate()
  const { createProject, loading, error } = useProjects()

  const [formData, setFormData] = useState({
    title: '',
    brief: '',
    brand_name: '',
    mood: 'uplifting',
    duration: 30,
    primary_color: '#4dbac7',
    secondary_color: '#ffffff',
    product_image_url: '',
  })

  const [productImage, setProductImage] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string>('')
  const [submitError, setSubmitError] = useState<string | null>(null)

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        setSubmitError('Image must be less than 10MB')
        return
      }

      // Validate file type
      if (!file.type.startsWith('image/')) {
        setSubmitError('Please select an image file')
        return
      }

      setProductImage(file)
      setSubmitError(null)

      // Create preview
      const reader = new FileReader()
      reader.onload = (e) => {
        setImagePreview(e.target?.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleRemoveImage = () => {
    setProductImage(null)
    setImagePreview('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError(null)

    // Validation
    if (!formData.title.trim()) {
      setSubmitError('Project title is required')
      return
    }

    if (!formData.brief.trim()) {
      setSubmitError('Product brief is required')
      return
    }

    if (!formData.brand_name.trim()) {
      setSubmitError('Brand name is required')
      return
    }

    if (formData.duration < 15 || formData.duration > 120) {
      setSubmitError('Duration must be between 15 and 120 seconds')
      return
    }

    try {
      const newProject = await createProject({
        title: formData.title,
        brief: formData.brief,
        brand_name: formData.brand_name,
        mood: formData.mood,
        duration: formData.duration,
        primary_color: formData.primary_color,
        secondary_color: formData.secondary_color || undefined,
        product_image_url: formData.product_image_url || undefined,
      })

      // Redirect to progress page
      navigate(`/projects/${newProject.id}/progress`)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create project'
      setSubmitError(message)
    }
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 flex flex-col">
      {/* Header */}
      <Header logo="GenAds" title="Create Project" />

      {/* Main Content */}
      <div className="flex-1">
        <Container size="md" className="py-12">
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-8"
          >
            {/* Title */}
            <motion.div variants={itemVariants}>
              <h2 className="text-3xl font-bold text-slate-100">New Project</h2>
              <p className="text-slate-400 mt-2">
                Create a new video project. Fill in the details below and we'll generate
                your ads.
              </p>
            </motion.div>

            {/* Form Card */}
            <motion.div variants={itemVariants}>
              <Card variant="glass">
                <CardHeader>
                  <CardTitle>Project Details</CardTitle>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSubmit} className="space-y-6">
                    {/* Error Message */}
                    {(error || submitError) && (
                      <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
                        {error || submitError}
                      </div>
                    )}

                    {/* Project Title */}
                    <Input
                      label="Project Title"
                      placeholder="e.g., Premium Skincare - Summer Campaign"
                      value={formData.title}
                      onChange={(e) =>
                        setFormData({ ...formData, title: e.target.value })
                      }
                      required
                    />

                    {/* Brand Name */}
                    <Input
                      label="Brand Name"
                      placeholder="Your brand name"
                      value={formData.brand_name}
                      onChange={(e) =>
                        setFormData({ ...formData, brand_name: e.target.value })
                      }
                      required
                    />

                    {/* Product Brief */}
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-2">
                        Product Brief
                      </label>
                      <textarea
                        placeholder="Describe your product, key features, and target audience. Example: A premium hydrating serum for mature skin with hyaluronic acid. Perfect for skincare influencers and beauty-conscious women 30-55."
                        value={formData.brief}
                        onChange={(e) =>
                          setFormData({ ...formData, brief: e.target.value })
                        }
                        rows={4}
                        className="w-full px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
                        required
                      />
                      <p className="text-xs text-slate-500 mt-1">
                        The more details, the better the generated video
                      </p>
                    </div>

                    {/* Mood */}
                    <Select
                      label="Video Mood"
                      options={moods}
                      value={String(formData.mood)}
                      onChange={(value) =>
                        setFormData({ ...formData, mood: value as string })
                      }
                    />

                    {/* Duration */}
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-2">
                        Video Duration (seconds)
                      </label>
                      <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="15"
                        max="120"
                        step="5"
                        value={String(formData.duration)}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            duration: parseInt(e.target.value),
                          })
                        }
                          className="flex-1 h-2 bg-slate-800 rounded-lg accent-indigo-600 cursor-pointer"
                        />
                        <div className="w-20 text-center">
                          <span className="text-2xl font-bold text-indigo-400">
                            {formData.duration}s
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-500 mt-2">
                        Recommended: 15-60 seconds for social media
                      </p>
                    </div>

                    {/* Brand Colors */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Primary Color
                        </label>
                        <div className="flex items-center gap-3">
                          <input
                            type="color"
                            value={formData.primary_color}
                            onChange={(e) =>
                              setFormData({ ...formData, primary_color: e.target.value })
                            }
                            className="h-10 w-16 rounded-lg border border-slate-700 cursor-pointer"
                          />
                          <input
                            type="text"
                            value={formData.primary_color}
                            onChange={(e) =>
                              setFormData({ ...formData, primary_color: e.target.value })
                            }
                            placeholder="#4dbac7"
                            className="flex-1 px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-sm"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Secondary Color (Optional)
                        </label>
                        <div className="flex items-center gap-3">
                          <input
                            type="color"
                            value={formData.secondary_color}
                            onChange={(e) =>
                              setFormData({ ...formData, secondary_color: e.target.value })
                            }
                            className="h-10 w-16 rounded-lg border border-slate-700 cursor-pointer"
                          />
                          <input
                            type="text"
                            value={formData.secondary_color}
                            onChange={(e) =>
                              setFormData({ ...formData, secondary_color: e.target.value })
                            }
                            placeholder="#ffffff"
                            className="flex-1 px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-sm"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Product Image Upload */}
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-2">
                        Product Image (Optional)
                      </label>
                      {imagePreview ? (
                        <div className="relative w-full">
                          <img
                            src={imagePreview}
                            alt="Product preview"
                            className="w-full h-48 object-cover rounded-lg border border-slate-700"
                          />
                          <button
                            type="button"
                            onClick={handleRemoveImage}
                            className="absolute top-2 right-2 p-1 bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
                          >
                            <X className="w-4 h-4 text-white" />
                          </button>
                        </div>
                      ) : (
                        <label className="flex items-center justify-center w-full h-32 border-2 border-dashed border-slate-700 rounded-lg cursor-pointer hover:bg-slate-800/50 transition-colors">
                          <div className="flex flex-col items-center justify-center">
                            <Upload className="w-8 h-8 text-slate-500 mb-2" />
                            <span className="text-sm text-slate-400">
                              Click to upload product image
                            </span>
                            <span className="text-xs text-slate-500 mt-1">
                              PNG, JPG, WebP (Max 10MB)
                            </span>
                          </div>
                          <input
                            type="file"
                            accept="image/*"
                            onChange={handleImageChange}
                            className="hidden"
                          />
                        </label>
                      )}
                    </div>

                    {/* Submit Buttons */}
                    <div className="flex gap-4 pt-6 border-t border-slate-700">
                      <Button
                        type="button"
                        variant="outline"
                        fullWidth
                        onClick={() => navigate('/dashboard')}
                        disabled={loading}
                      >
                        Cancel
                      </Button>
                  <Button
                    type="submit"
                    variant="gradient"
                    fullWidth
                  >
                    {loading ? 'Creating...' : 'Create Project'}
                  </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            </motion.div>

            {/* Info Box */}
            <motion.div
              variants={itemVariants}
              className="p-4 bg-indigo-500/10 border border-indigo-500/50 rounded-lg"
            >
              <p className="text-indigo-400 text-sm">
                💡 <strong>Pro Tip:</strong> Detailed product briefs result in better
                videos. Include key features, benefits, and target audience.
              </p>
            </motion.div>
          </motion.div>
        </Container>
      </div>
    </div>
  )
}

