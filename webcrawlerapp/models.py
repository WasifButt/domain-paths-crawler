from django.db import models

class Domain(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class Path(models.Model):
    id = models.AutoField(primary_key=True)
    path = models.CharField(max_length=500)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='paths')

    def __str__(self):
        return f"{self.domain.name}{self.path}"

    class Meta:
        ordering = ['path']
        unique_together = ['domain', 'path']