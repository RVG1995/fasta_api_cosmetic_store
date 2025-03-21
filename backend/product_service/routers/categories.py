from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Annotated

from models import CategoryModel
from schema import CategorySchema, CategoryAddSchema, CategoryUpdateSchema
from database import get_session
from auth import require_admin, get_current_user
from cache import cache_get, cache_set, cache_delete_pattern, CACHE_KEYS, CACHE_TTL, invalidate_cache

import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("categories_router")

# Создание роутера
router = APIRouter(
    prefix="/categories",
    tags=["categories"],
    responses={404: {"description": "Not found"}},
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

@router.get('', response_model=List[CategorySchema])
async def get_categories(session: SessionDep):
    # Формируем ключ кэша
    cache_key = f"{CACHE_KEYS['categories']}all"
    
    # Пробуем получить данные из кэша
    cached_data = await cache_get(cache_key)
    if cached_data:
        logger.info(f"Данные категорий получены из кэша: {cache_key}")
        return cached_data
    
    # Если данных в кэше нет, делаем запрос к БД
    query = select(CategoryModel).order_by(CategoryModel.name)
    result = await session.execute(query)
    categories = result.scalars().all()
    
    # Преобразуем для кэширования и сохраняем
    categories_list = [cat.__dict__ for cat in categories]
    for cat in categories_list:
        if '_sa_instance_state' in cat:
            del cat['_sa_instance_state']
    
    # Сохраняем в кэш
    await cache_set(cache_key, categories_list, CACHE_TTL)
    
    return categories

@router.post('', response_model=CategorySchema)
async def add_category(
    category_data: CategoryAddSchema,
    session: SessionDep,
    admin = Depends(require_admin)
):
    # Создаем новую категорию
    new_category = CategoryModel(**category_data.model_dump())
    
    # Добавляем в БД
    session.add(new_category)
    
    try:
        await session.commit()
        await session.refresh(new_category)
        
        # Инвалидируем кэш категорий
        await invalidate_cache(f"{CACHE_KEYS['categories']}*")
        
        return new_category
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Ошибка при добавлении категории: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Категория с таким названием уже существует"
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Неизвестная ошибка при добавлении категории: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при добавлении категории"
        )

@router.put("/{category_id}", response_model=CategorySchema)
async def update_category(
    category_id: int, 
    category_data: CategoryUpdateSchema,
    session: SessionDep,
    admin = Depends(require_admin)
):
    # Находим категорию по ID
    query = select(CategoryModel).where(CategoryModel.id == category_id)
    result = await session.execute(query)
    category = result.scalars().first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    
    # Обновляем поля категории
    for field, value in category_data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    
    try:
        await session.commit()
        await session.refresh(category)
        
        # Инвалидируем кэш категорий и связанных продуктов
        await invalidate_cache(f"{CACHE_KEYS['categories']}*")
        await invalidate_cache(f"{CACHE_KEYS['products']}*")
        
        return category
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Ошибка при обновлении категории: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Категория с таким названием уже существует"
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Неизвестная ошибка при обновлении категории: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при обновлении категории"
        )

@router.get('/{category_id}', response_model=CategorySchema)
async def get_category_by_id(category_id: int, session: SessionDep):
    # Формируем ключ кэша
    cache_key = f"{CACHE_KEYS['categories']}{category_id}"
    
    # Пробуем получить данные из кэша
    cached_data = await cache_get(cache_key)
    if cached_data:
        logger.info(f"Данные категории получены из кэша: {cache_key}")
        return cached_data
    
    # Если данных в кэше нет, делаем запрос к БД
    query = select(CategoryModel).where(CategoryModel.id == category_id)
    result = await session.execute(query)
    category = result.scalars().first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    
    # Преобразуем для кэширования
    category_dict = category.__dict__.copy()
    if '_sa_instance_state' in category_dict:
        del category_dict['_sa_instance_state']
    
    # Сохраняем в кэш
    await cache_set(cache_key, category_dict, CACHE_TTL)
    
    return category

@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    session: SessionDep,
    admin = Depends(require_admin)
):
    # Находим категорию по ID
    query = select(CategoryModel).where(CategoryModel.id == category_id)
    result = await session.execute(query)
    category = result.scalars().first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    
    # Удаляем категорию
    try:
        await session.delete(category)
        await session.commit()
        
        # Инвалидируем кэш категорий и связанных продуктов
        await invalidate_cache(f"{CACHE_KEYS['categories']}*")
        await invalidate_cache(f"{CACHE_KEYS['products']}*")
        
        return None
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно удалить категорию, т.к. существуют связанные записи"
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Неизвестная ошибка при удалении категории: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при удалении категории"
        )
