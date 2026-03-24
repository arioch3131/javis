"""
SQLAlchemy ORM Models for Content Items.

This module defines the SQLAlchemy ORM models for various content types
(images, documents, videos, audio) within the application. It implements
single-table inheritance for content items, allowing for flexible metadata
storage and efficient querying. It also includes models for tags and collections
to facilitate content organization.
"""

import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import backref, relationship

from ai_content_classifier.models.base import Base

# Conditional import for datetime_utcnow based on Python version for timezone awareness.
if sys.version_info >= (3, 12):

    def datetime_utcnow():
        """
        Returns the current UTC datetime without timezone information.
        Compatible with Python 3.12+.
        """
        return datetime.now(timezone.utc).replace(tzinfo=None)

else:

    def datetime_utcnow():
        """
        Returns the current UTC datetime without timezone information.
        Compatible with Python versions prior to 3.12.
        """
        return datetime.utcnow


# Association table for many-to-many relationship between ContentItem and Tag.
content_tags = Table(
    "content_tags",
    Base.metadata,
    Column(
        "content_id",
        Integer,
        ForeignKey("content_items.id"),
        primary_key=True,
        doc="Foreign key to the content_items table.",
    ),
    Column(
        "tag_id",
        Integer,
        ForeignKey("tags.id"),
        primary_key=True,
        doc="Foreign key to the tags table.",
    ),
)

# Association table for many-to-many relationship between Collection and ContentItem.
collection_contents = Table(
    "collection_contents",
    Base.metadata,
    Column(
        "collection_id",
        Integer,
        ForeignKey("collections.id"),
        primary_key=True,
        doc="Foreign key to the collections table.",
    ),
    Column(
        "content_id",
        Integer,
        ForeignKey("content_items.id"),
        primary_key=True,
        doc="Foreign key to the content_items table.",
    ),
)


class Tag(Base):
    """
    SQLAlchemy ORM model representing a tag for content items.

    Attributes:
        id (int): Primary key, unique identifier for the tag.
        name (str): The name of the tag, must be unique and not null.
    """

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, doc="Unique identifier for the tag.")
    name = Column(
        String(100), nullable=False, unique=True, index=True, doc="The name of the tag."
    )

    def __repr__(self) -> str:
        """
        Returns a string representation of the Tag object.
        """
        return f"<Tag(id={self.id}, name='{self.name}')>"


class Collection(Base):
    """
    SQLAlchemy ORM model representing a collection of content items.

    Collections can be nested, forming a hierarchical structure.

    Attributes:
        id (int): Primary key, unique identifier for the collection.
        name (str): The name of the collection.
        description (str, optional): A brief description of the collection.
        date_created (datetime): The UTC timestamp when the collection was created.
        date_modified (datetime): The UTC timestamp when the collection was last modified.
        parent_id (int, optional): Foreign key to the parent collection, enabling nesting.
        parent (Collection): Relationship to the parent collection.
        subcollections (list[Collection]): Relationship to child collections.
        contents (list[ContentItem]): Relationship to content items within this collection.
    """

    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, doc="Unique identifier for the collection.")
    name = Column(String(255), nullable=False, doc="The name of the collection.")
    description = Column(Text, nullable=True, doc="A description of the collection.")
    date_created = Column(
        DateTime, default=datetime_utcnow, doc="UTC timestamp of creation."
    )
    date_modified = Column(
        DateTime,
        default=datetime_utcnow,
        onupdate=datetime_utcnow,
        doc="UTC timestamp of last modification.",
    )
    parent_id = Column(
        Integer,
        ForeignKey("collections.id"),
        nullable=True,
        doc="Foreign key to the parent collection for hierarchical organization.",
    )

    # Relationships
    parent = relationship(
        "Collection",
        remote_side=[id],
        backref=backref("subcollections"),
        doc="Parent collection in a hierarchical structure.",
    )
    contents = relationship(
        "ContentItem",
        secondary=collection_contents,
        back_populates="collections",
        doc="Content items belonging to this collection.",
    )

    def __repr__(self) -> str:
        """
        Returns a string representation of the Collection object.
        """
        return f"<Collection(id={self.id}, name='{self.name}')>"


class ContentItem(Base):
    """
    Base SQLAlchemy ORM model for all content items (images, documents, videos, audio).

    This model implements single-table inheritance using the `content_type` column
    as the discriminator. It provides common attributes shared across all content types
    and a flexible JSON field for additional metadata.

    Attributes:
        id (int): Primary key, unique identifier for the content item.
        uuid (str): A unique UUID for the content item, generated automatically.
        path (str): The absolute file path of the content item, must be unique.
        filename (str): The name of the file.
        directory (str): The directory containing the file.
        category (str, optional): The assigned category for the content item.
        date_created (datetime): The UTC timestamp when the file was created.
        date_modified (datetime): The UTC timestamp when the file was last modified.
        date_indexed (datetime): The UTC timestamp when the content item was indexed.
        file_size (int, optional): The size of the file in bytes.
        file_hash (str, optional): A hash of the file content for deduplication purposes.
        content_type (str): Discriminator column for single-table inheritance (e.g., 'image', 'document').
        metadata_extracted (bool): Flag indicating if metadata has been extracted for this item.
        width (int, optional): Width of the content (for images/videos).
        height (int, optional): Height of the content (for images/videos).
        format (str, optional): File format (e.g., 'jpeg', 'pdf').
        duration (int, optional): Duration of the content in seconds (for audio/video).
        content_metadata (dict, optional): A JSON field for storing arbitrary, flexible metadata.
        tags (list[Tag]): Relationship to associated tags.
        collections (list[Collection]): Relationship to collections this item belongs to.
    """

    __tablename__ = "content_items"

    id = Column(
        Integer, primary_key=True, doc="Unique identifier for the content item."
    )
    uuid = Column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        doc="Unique UUID for the content item.",
    )
    path = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
        doc="Absolute file path of the content item.",
    )
    filename = Column(String, nullable=False, doc="Name of the file.")
    directory = Column(String, nullable=False, doc="Directory containing the file.")
    category = Column(
        String, nullable=True, index=True, doc="Assigned category for the content item."
    )
    classification_confidence = Column(
        Float,
        nullable=True,
        doc="Confidence score associated with the assigned category.",
    )
    date_created = Column(
        DateTime, default=datetime_utcnow, doc="UTC timestamp of file creation."
    )
    date_modified = Column(
        DateTime,
        default=datetime_utcnow,
        onupdate=datetime_utcnow,
        doc="UTC timestamp of last file modification.",
    )
    date_indexed = Column(
        DateTime,
        default=datetime_utcnow,
        doc="UTC timestamp when the item was indexed.",
    )
    file_size = Column(Integer, nullable=True, doc="Size of the file in bytes.")
    file_hash = Column(
        String(64),
        nullable=True,
        index=True,
        doc="SHA-256 hash of the file for deduplication.",
    )
    content_type = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Discriminator for single-table inheritance (e.g., 'image', 'document').",
    )
    metadata_extracted = Column(
        Boolean,
        default=False,
        index=True,
        doc="Flag indicating if metadata has been extracted.",
    )

    # Common media dimensions - shared between Image and Video
    width = Column(Integer, nullable=True, doc="Width of the content in pixels.")
    height = Column(Integer, nullable=True, doc="Height of the content in pixels.")
    format = Column(String, nullable=True, doc="File format (e.g., 'jpeg', 'pdf').")

    # Common audio/video properties - shared between Audio and Video
    duration = Column(Integer, nullable=True, doc="Duration of the content in seconds.")

    # JSON field for flexible metadata storage
    content_metadata = Column(
        JSON, nullable=True, doc="Flexible JSON field for additional metadata."
    )

    # Relationships
    tags = relationship(
        "Tag",
        secondary=content_tags,
        backref="content_items",
        doc="Tags associated with this content item.",
    )
    collections = relationship(
        "Collection",
        secondary=collection_contents,
        back_populates="contents",
        doc="Collections this content item belongs to.",
    )

    # Indexes for common queries to improve performance.
    __table_args__ = (
        Index("idx_content_type_category", "content_type", "category"),
        Index("idx_content_metadata_extracted", "metadata_extracted"),
    )

    # Mapper arguments for single-table inheritance.
    __mapper_args__ = {
        "polymorphic_on": content_type,
        "polymorphic_identity": "content_item",
    }

    # Specific properties for subclasses, defined in the base class as nullable
    year_taken = Column(Integer, nullable=True, doc="The year the image was taken.")
    language = Column(String, nullable=True, doc="The language of the document.")
    page_count = Column(
        Integer, nullable=True, doc="The number of pages in the document."
    )
    text_content = Column(
        Text, nullable=True, doc="The extracted text content of the document."
    )
    bit_rate = Column(Integer, nullable=True, doc="The audio bit rate in kbps.")
    sample_rate = Column(Integer, nullable=True, doc="The audio sample rate in Hz.")

    def __repr__(self) -> str:
        """
        Returns a string representation of the ContentItem object.
        """
        return f"<ContentItem(id={self.id}, path='{self.path}', type='{self.content_type}')>"


class Image(ContentItem):
    """
    SQLAlchemy ORM model for image content items.

    Inherits from `ContentItem` and specifies the polymorphic identity for images.

    Attributes:
        year_taken (int, optional): The year the image was taken.
    """

    # No need for __tablename__ as it uses single-table inheritance from ContentItem.

    __mapper_args__ = {"polymorphic_identity": "image"}

    def __repr__(self) -> str:
        """
        Returns a string representation of the Image object.
        """
        return f"<Image(id={self.id}, path='{self.path}', dimensions='{self.width}x{self.height}')>"


class Document(ContentItem):
    """
    SQLAlchemy ORM model for document content items.

    Inherits from `ContentItem` and specifies the polymorphic identity for documents.

    Attributes:
        language (str, optional): The language of the document (e.g., 'en', 'fr').
        page_count (int, optional): The number of pages in the document.
        text_content (str, optional): The extracted text content of the document.
    """

    # No need for __tablename__ as it uses single-table inheritance from ContentItem.

    __mapper_args__ = {"polymorphic_identity": "document"}

    def __repr__(self) -> str:
        """
        Returns a string representation of the Document object.
        """
        return f"<Document(id={self.id}, path='{self.path}', pages={self.page_count})>"


class Video(ContentItem):
    """
    SQLAlchemy ORM model for video content items.

    Inherits from `ContentItem` and specifies the polymorphic identity for videos.
    """

    # No need for __tablename__ as it uses single-table inheritance from ContentItem.

    __mapper_args__ = {"polymorphic_identity": "video"}

    def __repr__(self) -> str:
        """
        Returns a string representation of the Video object.
        """
        return f"<Video(id={self.id}, path='{self.path}', duration='{self.duration}s')>"


class Audio(ContentItem):
    """
    SQLAlchemy ORM model for audio content items.

    Inherits from `ContentItem` and specifies the polymorphic identity for audio.

    Attributes:
        bit_rate (int, optional): The audio bit rate in kbps.
        sample_rate (int, optional): The audio sample rate in Hz.
    """

    # No need for __tablename__ as it uses single-table inheritance from ContentItem.

    __mapper_args__ = {"polymorphic_identity": "audio"}

    def __repr__(self) -> str:
        """
        Returns a string representation of the Audio object.
        """
        return f"<Audio(id={self.id}, path='{self.path}', duration='{self.duration}s')>"
